"""Save a real screenshot of the React board (Vite at :5173) opened on one ticket.

    .venv/bin/python scripts/screenshot_board.py 102 output/screenshots/ticket_102.png
"""

import sys

from playwright.sync_api import sync_playwright

BOARD = "http://localhost:5173"


def main(ticket_id: int, out: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto(f"{BOARD}/?ticket={ticket_id}")
        page.wait_for_selector(f".ticket-head .th-no:has-text('Ticket No. {ticket_id}')")
        page.wait_for_selector(".feed-row", timeout=15000)  # events loaded
        page.add_style_tag(content=".tape { max-height: none !important; }")  # show the whole run
        page.wait_for_timeout(2500)  # let stamps / needle settle
        page.screenshot(path=out, full_page=True)
        browser.close()
    print(f"saved {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
