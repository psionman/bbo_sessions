import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bbo_tournaments import logger
from bbo_tournaments.playwright_launch import launch_chromium

load_dotenv()

BBO_LOGIN_URL = "https://www.bridgebase.com/v3/auth/login"
SESSION_FILE = Path("bbo_session.json")

BBO_USERNAME = os.getenv("BBO_USERNAME")
BBO_PASSWORD = os.getenv("BBO_PASSWORD")

SESSION_PATTERN = re.compile(r"#(\d+)\s+.*?\b(\d{1,2} [A-Za-z]+ \d{4})\b")
COOKIE_BUTTON = re.compile(r"accept|agree|allow", re.IGNORECASE)
COOKIE_TIMEOUT = 1000

LOGIN_TIMEOUT = 15  # Seconds to wait for BBO to accept the login
SCREEN_SHOTS = "screenshots"
FAILURE_SHOT = Path(SCREEN_SHOTS, "login_failed.png")


class WebSessionError(Exception):
    """Exception raised for web session-related errors."""


class BboPhoenixSession:
    """Own the browser so it stays open between button clicks."""

    def __init__(self, headless: bool = True) -> None:
        self._playwright = sync_playwright().start()
        self._browser = launch_chromium(self._playwright, headless=headless)
        self.logged_in = False
        try:
            self._context = self._browser.new_context(
                viewport={"width": 1700, "height": 900}
            )
        except Exception as e:
            logger.error(f"Failed to create browser context: {e}")
            raise
        self.page: Page = self._context.new_page()
        # Set Chromium page zoom to 75%
        # cdp = self._context.new_cdp_session(self.page)
        # cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 0.75})
        logger.info("Browser initialized")

    def login(self) -> None:
        if self.logged_in:
            return
        page = self.page
        logger.info("Starting login process")
        try:
            page.goto(
                BBO_LOGIN_URL, wait_until="domcontentloaded", timeout=20000
            )
            page.locator("#username").wait_for(timeout=10000)
        except PlaywrightTimeoutError as error:
            self._fail("BBO did not load in time.", error)
        except PlaywrightError as error:
            self._fail(f"Could not reach BBO: {error}", error)

        logger.info("Page loaded, accepting cookies")
        self._accept_cookies(page)
        try:
            self._enter_credentials(BBO_USERNAME, BBO_PASSWORD)
        except PlaywrightError as error:
            self._fail("Could not fill in the login form.", error)

        self._wait_for_login()
        self._context.storage_state(path=SESSION_FILE)
        self.logged_in = True
        logger.info("Logged in")

    def _login_succeeded(self) -> bool:
        """True once BBO has left the login page or shows the main menu."""
        page = self.page
        if "/auth/login" not in page.url:
            return True
        return page.locator("tab-bar-button:visible").count() > 0

    def _wait_for_login(self, timeout: float = LOGIN_TIMEOUT) -> None:
        """Poll for success; fail clearly, and quickly, if it never comes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._login_succeeded():
                    return
            except PlaywrightError as error:  # The page closed or navigated
                self._fail("The browser closed during login.", error)
            self.page.wait_for_timeout(250)

        try:
            seen = self.page.locator("body").inner_text()[:300]
        except PlaywrightError:
            seen = "(could not read the page)"
        logger.warning("Login page said: %r", seen)
        self._fail(
            "BBO did not accept the login (wrong password, a captcha, "
            f"or a slow site). Page text: {seen!r}"
        )

    def _fail(self, message: str, error: Exception | None = None) -> None:
        """Log, take a screenshot, close the session and raise."""
        logger.error(message)
        try:
            self.page.screenshot(path=FAILURE_SHOT)
        except PlaywrightError:
            pass  # Page already gone
        self.close()
        raise WebSessionError(message) from error

    def _enter_credentials(self, username: str, password: str) -> None:
        page = self.page
        # page.on(
        #     "request",
        #     lambda r: (
        #         logger.info("REQ %s %s", r.method, r.url[:100])
        #         if "auth" in r.url or r.method == "POST"
        #         else None
        #     ),
        # )
        # page.on(
        #     "response",
        #     lambda r: (
        #         logger.info("RES %s %s", r.status, r.url[:100])
        #         if "auth" in r.url or r.request.method == "POST"
        #         else None
        #     ),
        # )
        # page.on(
        #     "console",
        #     lambda m: (
        #         logger.info("CONSOLE %s %s", m.type, m.text[:200])
        #         if m.type in ("error", "warning")
        #         else None
        #     ),
        # )

        user_box = page.locator("#username")
        password_box = page.locator("#password")
        user_box.fill(username)
        password_box.fill(password)
        # logger.info(
        #     "lengths: user=%d password=%d | user maxlength=%s",
        #     len(user_box.input_value()),
        #     len(password_box.input_value()),
        #     user_box.get_attribute("maxlength"),
        # )

        sign_in = page.get_by_role("button", name="Sign in", exact=True)
        # logger.info(
        #     "button count=%d enabled=%s",
        #     sign_in.count(),
        #     sign_in.is_enabled() if sign_in.count() else None,
        # )
        sign_in.click(timeout=5000)
        page.wait_for_timeout(3000)
        # logger.info("url after click: %s", page.url)
        page.screenshot(path=Path(SCREEN_SHOTS, "after_signin_click.png"))

    def _accept_cookies(self, page: Page) -> None:
        """Click the cookie consent button if one appears."""
        button = page.get_by_role("button", name=COOKIE_BUTTON).first
        try:
            button.click(timeout=COOKIE_TIMEOUT)
        except PlaywrightTimeoutError:
            logger.debug("No cookie banner found")
            pass  # No banner this time

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()
