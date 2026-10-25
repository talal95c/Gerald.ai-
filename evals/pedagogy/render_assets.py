"""Render the pedagogy scenario pages to 1440x900 PNGs and record target boxes (screen pixels)."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
PAGES = HERE / "pages"
ASSETS = HERE / "assets"


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    targets: dict[str, dict[str, list[float]]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp("http://localhost:29229")
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = context.new_page()
        for html in sorted(PAGES.glob("*.html")):
            page.goto(html.resolve().as_uri())
            page.wait_for_timeout(250)
            page.screenshot(path=str(ASSETS / f"{html.stem}.png"))
            boxes = {}
            for element in page.query_selector_all("[id]"):
                box = element.bounding_box()
                if box and box["width"] > 0 and box["height"] > 0:
                    boxes[element.get_attribute("id")] = [box["x"], box["y"], box["width"], box["height"]]
            targets[html.stem] = boxes
        context.close()
    (ASSETS / "targets.json").write_text(json.dumps(targets, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"rendered {len(targets)} pages")


if __name__ == "__main__":
    main()
