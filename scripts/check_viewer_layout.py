from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--url", default="http://127.0.0.1:8768")
    return result


def main() -> int:
    arguments = parser().parse_args()
    sizes = ((1600, 1200), (1024, 900), (390, 844))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in sizes:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(arguments.url, wait_until="networkidle")
            page.locator(".attempt.selected").wait_for()
            result = page.evaluate(
                """
                () => ({
                  documentWidth: document.documentElement.scrollWidth,
                  viewportWidth: window.innerWidth,
                  clipped: [...document.querySelectorAll('body *')]
                    .filter(node => {
                      const style = getComputedStyle(node);
                      if (style.display === 'none' || style.position === 'fixed') return false;
                      const box = node.getBoundingClientRect();
                      return box.left < -1 || box.right > window.innerWidth + 1;
                    })
                    .slice(0, 8)
                    .map(node => node.tagName.toLowerCase() + '.' + node.className)
                })
                """
            )
            if result["documentWidth"] > result["viewportWidth"] or result["clipped"]:
                raise AssertionError(f"{width}x{height}: {result}")
            print(f"PASS {width}x{height}")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
