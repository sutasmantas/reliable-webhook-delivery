"""Check that every consumer carries the artifact this provider actually builds.

Each consumer already commits a hash beside its vendored wheel and asserts the
file still matches it. That catches a corrupted or swapped file, but it cannot
catch the case that matters most: the provider moving on. A hash committed next
to a wheel says nothing about whether the provider still produces that wheel.

This closes that gap by rebuilding the provider from source and comparing the
result to what each consumer carries. It reports three distinct states, because
conflating them is how drift hides:

``current``      the vendored wheel equals a fresh provider build
``drifted``      the wheel is internally consistent but the provider has moved
``misrecorded``  the wheel does not match the hash committed beside it

Consumers record their hashes in three different formats. Rather than force a
migration, the checker reads all three, and reports the format it used so the
inconsistency stays visible instead of being silently absorbed.

Exit code is non-zero if any consumer is anything other than ``current``.

    python scripts/check_consumer_freshness.py ../pipeline_forge ../adapter_proof
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PROVIDER_ROOT = Path(__file__).resolve().parents[1]
WHEEL_GLOB = "deliveryguard-*-py3-none-any.whl"

#: Fixed so the build is byte-reproducible. Any value works as long as every
#: build uses the same one; without it, wheel timestamps make comparison
#: meaningless and real drift becomes indistinguishable from noise.
SOURCE_DATE_EPOCH = "1580601600"

PIN_PATTERN = re.compile(r"deliveryguard\s*==\s*([0-9][^\"',\s]*)")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class ConsumerReport:
    name: str
    root: Path
    state: str = "unknown"
    wheel: str | None = None
    wheel_sha256: str | None = None
    recorded_sha256: str | None = None
    record_format: str | None = None
    declared_pin: str | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "consumer": self.name,
            "state": self.state,
            "wheel": self.wheel,
            "wheel_sha256": self.wheel_sha256,
            "recorded_sha256": self.recorded_sha256,
            "record_format": self.record_format,
            "declared_pin": self.declared_pin,
            "notes": self.notes,
        }


def build_provider(root: Path, outdir: Path, *, ref: str = "HEAD", from_worktree: bool = False) -> Path:
    """Build the provider wheel reproducibly and return its path.

    The build runs against a pristine ``git archive`` export of ``ref``, not
    against the working tree, and that is not fussiness. A working copy can hold
    line endings that differ from what a fresh checkout of the same commit
    produces — git normalises on read, so it reports such a tree as clean while
    the bytes on disk, and therefore the bytes in the wheel, differ. Building
    from the working tree makes the answer depend on which checkout you happen
    to be standing in, and every consumer would be reported as drifted for a
    reason that has nothing to do with the provider.
    """

    if from_worktree:
        source = root
    else:
        export = outdir / "_export"
        export.mkdir(parents=True, exist_ok=True)
        archive = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", ref],
            check=True,
            capture_output=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            # `filter` landed in 3.12; the provider supports 3.10+.
            if sys.version_info >= (3, 12):
                tar.extractall(export, filter="data")
            else:
                tar.extractall(export)
        source = export

    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(outdir), str(source)],
        check=True,
        capture_output=True,
        env={**_clean_env(), "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH},
    )
    wheels = sorted(outdir.glob(WHEEL_GLOB))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one built wheel, found {len(wheels)}")
    return wheels[0]


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}


def find_recorded_hash(vendor: Path, wheel_name: str) -> tuple[str | None, str | None]:
    """Read the consumer's recorded hash in whichever format it uses."""

    # Format 1: a dedicated <wheel-stem>.sha256 file.
    for candidate in vendor.glob("deliveryguard-*.sha256"):
        first = candidate.read_text(encoding="utf-8").split()
        if first:
            return first[0], f"{candidate.name} (dedicated .sha256)"

    # Format 2: a multi-artifact SHA256SUMS manifest.
    manifest = vendor / "SHA256SUMS"
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == wheel_name:
                return parts[0], "SHA256SUMS (shared manifest)"

    # Format 3: the hash is asserted inline in a test rather than recorded as data.
    tests = vendor.parent / "tests"
    if tests.is_dir():
        for path in sorted(tests.glob("*.py")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "deliveryguard" not in text:
                continue
            match = re.search(r"[\"']([0-9a-f]{64})[\"']", text)
            if match:
                return match.group(1), f"tests/{path.name} (inline literal, not a data file)"

    return None, None


def declared_pin(root: Path) -> str | None:
    for name in ("pyproject.toml", "requirements.txt"):
        path = root / name
        if not path.exists():
            continue
        match = PIN_PATTERN.search(path.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return None


def check_consumer(root: Path, provider_sha: str, provider_version: str) -> ConsumerReport:
    report = ConsumerReport(name=root.name, root=root)
    vendor = root / "vendor"
    if not vendor.is_dir():
        report.state = "no-vendor-directory"
        report.notes.append("no vendor/ directory; consumer may resolve the provider from an index")
        return report

    wheels = sorted(vendor.glob(WHEEL_GLOB))
    if not wheels:
        report.state = "no-vendored-wheel"
        return report
    wheel = wheels[0]
    report.wheel = wheel.name
    report.wheel_sha256 = sha256_of(wheel)
    report.recorded_sha256, report.record_format = find_recorded_hash(vendor, wheel.name)
    report.declared_pin = declared_pin(root)

    if report.recorded_sha256 is None:
        report.notes.append("no committed hash found in any known format")
    elif report.recorded_sha256 != report.wheel_sha256:
        report.state = "misrecorded"
        report.notes.append("the vendored wheel does not match the hash committed beside it")
        return report

    if report.declared_pin and report.declared_pin != provider_version:
        report.notes.append(
            f"declared pin {report.declared_pin} does not match provider version {provider_version}"
        )

    if report.wheel_sha256 == provider_sha:
        report.state = "current"
    else:
        report.state = "drifted"
        report.notes.append(
            "the provider no longer builds this wheel; the vendored artifact predates provider changes"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consumers", nargs="+", help="paths to consumer project roots")
    parser.add_argument("--provider-root", default=str(PROVIDER_ROOT))
    parser.add_argument("--ref", default="HEAD", help="provider commit to build (default HEAD)")
    parser.add_argument(
        "--from-worktree",
        action="store_true",
        help="build from the working tree instead of a pristine export; "
        "only for diagnosing working-copy contamination",
    )
    parser.add_argument(
        "--verify-reproducible",
        action="store_true",
        help="build twice and fail unless both builds hash identically",
    )
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    provider_root = Path(args.provider_root).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        built = build_provider(
            provider_root, Path(tmp), ref=args.ref, from_worktree=args.from_worktree
        )
        provider_sha = sha256_of(built)
        provider_version = built.name.split("-")[1]

        if args.verify_reproducible:
            with tempfile.TemporaryDirectory() as second:
                again = build_provider(
                    provider_root, Path(second), ref=args.ref, from_worktree=args.from_worktree
                )
                if sha256_of(again) != provider_sha:
                    raise SystemExit(
                        "the provider build is not reproducible: two builds of the same "
                        f"source produced {provider_sha} and {sha256_of(again)}"
                    )

        reports = [
            check_consumer(Path(c).resolve(), provider_sha, provider_version)
            for c in args.consumers
        ]

    payload = {
        "provider_root": str(provider_root),
        "provider_version": provider_version,
        "provider_wheel_sha256": provider_sha,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "built_from": "working tree" if args.from_worktree else f"pristine export of {args.ref}",
        "consumers": [r.as_dict() for r in reports],
    }

    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"provider {provider_version} builds {provider_sha}")
        print(f"{'consumer':<22}{'state':<14}{'pin':<8}record")
        for r in reports:
            print(f"{r.name:<22}{r.state:<14}{r.declared_pin or '-':<8}{r.record_format or '-'}")
            for note in r.notes:
                print(f"    ! {note}")

    stale = [r for r in reports if r.state != "current"]
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
