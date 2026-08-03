from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--url", default="http://127.0.0.1:8768")
    result.add_argument(
        "--ffmpeg",
        type=Path,
        default=None,
    )
    return result


def inject_tour(page: Page) -> None:
    page.evaluate(
        """
        () => {
          const style = document.createElement('style');
          style.textContent = `
            #tour-caption { position:fixed; left:50%; top:34px; transform:translateX(-50%); z-index:9998; max-width:1120px; padding:18px 26px; color:white; background:#111722; border:1px solid white; box-shadow:8px 8px 0 #ff5a36; font:800 27px/1.2 Inter,system-ui,sans-serif; text-align:center; opacity:0; transition:opacity .28s ease; }
            #tour-cursor { position:fixed; left:110px; top:110px; z-index:9999; width:30px; height:30px; border:3px solid white; border-radius:50%; background:#ff5a36; box-shadow:0 2px 12px #0008; pointer-events:none; transition:left .55s ease, top .55s ease, transform .16s ease; }
            #tour-end { position:fixed; inset:0; z-index:10000; display:grid; place-items:center; color:white; background:#111722; opacity:0; pointer-events:none; transition:opacity .35s ease; }
            #tour-end div { width:min(920px,80vw); text-align:center; }
            #tour-end small { color:#74e4bc; font:800 13px/1 ui-monospace,monospace; letter-spacing:.14em; text-transform:uppercase; }
            #tour-end h2 { margin:20px 0; font-size:65px; line-height:.95; letter-spacing:-.055em; }
            #tour-end p { margin:0; color:#c2c8d2; font-size:22px; }
          `;
          document.head.append(style);
          const caption = document.createElement('div'); caption.id='tour-caption'; document.body.append(caption);
          const cursor = document.createElement('div'); cursor.id='tour-cursor'; document.body.append(cursor);
          const end = document.createElement('div'); end.id='tour-end'; end.innerHTML='<div><small>DeliveryGuard</small><h2>Recover webhook failures without duplicating actions.</h2><p>Bounded retries · durable receipts · dead letter · explicit replay</p></div>'; document.body.append(end);
        }
        """
    )


def caption(page: Page, value: str) -> None:
    page.evaluate(
        "value => { const node=document.querySelector('#tour-caption'); node.textContent=value; node.style.opacity='1'; }",
        value,
    )


def move_cursor(page: Page, selector: str, index: int = 0) -> None:
    box = page.locator(selector).nth(index).bounding_box()
    if box is None:
        return
    page.evaluate(
        "point => { const node=document.querySelector('#tour-cursor'); node.style.left=`${point.x}px`; node.style.top=`${point.y}px`; }",
        {"x": box["x"] + box["width"] * 0.72, "y": box["y"] + box["height"] * 0.45},
    )


def capture_images(page: Page, output: Path, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    page.locator(".attempt.selected").wait_for()
    page.add_style_tag(
        content="""
        body.capture-workflow .topbar, body.capture-workflow .hero { display:none; }
        body.capture-workflow main { padding-top:1px; }
        body.capture-workflow .recorder { margin-top:34px; }
        body.capture-workflow .proof-grid { display:none; }
        body.capture-workflow .contract { margin-top:22px; }
        body.capture-workflow .contract article { min-height:610px; padding:34px; }
        body.capture-workflow .contract article>b { margin-bottom:135px; }
        body.capture-workflow .contract h3 { font-size:25px; }
        body.capture-workflow .contract article p { font-size:14px; }
        body.capture-proof .topbar, body.capture-proof .hero, body.capture-proof .recorder, body.capture-proof .contract { display:none; }
        body.capture-proof main { padding-top:48px; }
        body.capture-proof .proof-grid { grid-template-columns:1.12fr .88fr; margin-top:0; }
        body.capture-proof .receipt-panel, body.capture-proof .recovery-panel { min-height:1035px; }
        body.capture-proof .receipt-panel { display:flex; flex-direction:column; }
        body.capture-proof .receipt-title { padding-top:44px; }
        body.capture-proof pre { flex:1; display:flex; align-items:center; min-height:650px; padding:48px; font-size:18px; line-height:1.75; }
        body.capture-proof .recovery-panel { display:flex; flex-direction:column; justify-content:center; padding:50px; }
        body.capture-proof .recovery-panel h2 { font-size:46px; }
        body.capture-proof .cycle-map { margin:55px 0; }
        body.capture-proof .cycle-map > div { padding:28px; }
        body.capture-proof .cycle-map strong { font-size:45px; }
        body.capture-proof .recovery-panel li { padding:22px; }
        """
    )
    page.evaluate("scrollTo(0,0)")
    page.screenshot(path=output / "01_cover.png")
    page.locator(".attempt.retry").click()
    page.evaluate("document.body.classList.add('capture-workflow'); scrollTo(0,0)")
    page.screenshot(path=output / "02_workflow.png")
    page.evaluate("document.body.classList.remove('capture-workflow')")
    page.locator(".attempt.terminal").click()
    page.evaluate("document.body.classList.add('capture-proof'); scrollTo(0,0)")
    page.screenshot(path=output / "03_proof.png")


def capture_video(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    page.locator(".attempt.selected").wait_for()
    inject_tour(page)
    caption(page, "A 503 is classified as transient before DeliveryGuard retries it.")
    page.wait_for_timeout(2300)
    page.evaluate("scrollTo({top:430,behavior:'smooth'})")
    move_cursor(page, ".attempt.retry")
    page.wait_for_timeout(900)
    page.locator(".attempt.retry").click()
    page.wait_for_timeout(1800)
    caption(
        page,
        "The retry succeeds—and the duplicate reuses the action with zero extra calls.",
    )
    move_cursor(page, ".attempt.success", 0)
    page.wait_for_timeout(900)
    page.locator(".attempt.success").nth(0).click()
    page.wait_for_timeout(2200)
    caption(
        page,
        "A permanent 422 stops immediately and becomes an inspectable dead letter.",
    )
    move_cursor(page, ".attempt.terminal")
    page.wait_for_timeout(900)
    page.locator(".attempt.terminal").click()
    page.evaluate("scrollTo({top:820,behavior:'smooth'})")
    page.wait_for_timeout(2300)
    caption(
        page,
        "Explicit replay starts cycle 2 and preserves the complete receipt history.",
    )
    move_cursor(page, ".attempt.success", 1)
    page.wait_for_timeout(800)
    page.locator(".attempt.success").nth(1).click()
    page.wait_for_timeout(2600)
    page.evaluate("document.querySelector('#tour-end').style.opacity='1'")
    page.wait_for_timeout(2300)


def main() -> int:
    arguments = parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "final_upload"
    video_tmp = root / ".capture_video"
    output.mkdir(exist_ok=True)
    if video_tmp.exists():
        shutil.rmtree(video_tmp)
    video_tmp.mkdir()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        image_page = browser.new_page(viewport={"width": 1600, "height": 1200})
        capture_images(image_page, output, arguments.url)
        browser.close()

        context = playwright.chromium.launch(headless=True).new_context(
            viewport={"width": 1600, "height": 1200},
            record_video_dir=video_tmp,
            record_video_size={"width": 1600, "height": 1200},
        )
        video_page = context.new_page()
        capture_video(video_page, arguments.url)
        video = video_page.video
        context.close()
        source = video.path()
    destination = output / "04_deliveryguard_walkthrough.mp4"
    if arguments.ffmpeg is None:
        raise ValueError("--ffmpeg must point to an H.264-capable FFmpeg binary")
    ffmpeg = arguments.ffmpeg
    subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(video_tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
