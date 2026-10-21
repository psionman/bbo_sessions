from playwright.sync_api import sync_playwright

LOGIN_URL = "https://www.bridgebase.com/v3/auth/login"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    page.screenshot(path="login.png")
    for html in page.locator("input").evaluate_all(
        "els => els.map(e => e.outerHTML)"
    ):
        print(html)
    print([frame.url for frame in page.frames])
    input("Press Enter to close...")
    browser.close()
