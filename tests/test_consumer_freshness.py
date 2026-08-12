from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from scripts.check_consumer_freshness import sha256_of, wheel_content_sha256

if TYPE_CHECKING:
    from pathlib import Path


def _wheel(path: Path, members: list[tuple[str, bytes]], compression: int) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as wheel:
        for name, content in members:
            wheel.writestr(name, content)


def test_content_hash_ignores_zip_order_and_compression(tmp_path: Path) -> None:
    members = [("package/a.py", b"A"), ("package/b.py", b"B")]
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    _wheel(first, members, zipfile.ZIP_STORED)
    _wheel(second, list(reversed(members)), zipfile.ZIP_DEFLATED)

    assert sha256_of(first) != sha256_of(second)
    assert wheel_content_sha256(first) == wheel_content_sha256(second)


def test_content_hash_detects_changed_member(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    _wheel(first, [("package/a.py", b"A")], zipfile.ZIP_STORED)
    _wheel(second, [("package/a.py", b"changed")], zipfile.ZIP_STORED)

    assert wheel_content_sha256(first) != wheel_content_sha256(second)
