import os
import re
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bbo_sessions import logger
from bbo_sessions.playwright_launch import launch_chromium

load_dotenv()

BBO_LOGIN_URL = "https://www.bridgebase.com/v3/auth/login"
SESSION_FILE = Path("bbo_session.json")

BBO_USERNAME = os.getenv("BBO_USERNAME")
BBO_PASSWORD = os.getenv("BBO_PASSWORD")

SESSION_PATTERN = re.compile(r"#(\d+)\s+.*?\b(\d{1,2} [A-Za-z]+ \d{4})\b")
COOKIE_BUTTON = re.compile(r"accept|agree|allow", re.IGNORECASE)
COOKIE_TIMEOUT = 1000


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
        page = self.page
        if self.logged_in:
            return

        try:
            page.goto(
                BBO_LOGIN_URL, wait_until="domcontentloaded", timeout=30000
            )
            page.locator("#username").wait_for(timeout=15000)
        except PlaywrightTimeoutError as error:
            logger.error("BBO did not load in time")
            self.close()
            raise WebSessionError(
                "BBO did not load in time. Check your connection and "
                "try again."
            ) from error
        except PlaywrightError as error:
            logger.error(f"Could not reach BBO: {error}")
            self.close()
            raise WebSessionError(f"Could not reach BBO: {error}") from error

        self._accept_cookies(page)

        self._enter_credentials(BBO_USERNAME, BBO_PASSWORD)
        page.wait_for_url(lambda url: "/auth/login" not in url)
        # page.add_style_tag(content="body { zoom: 75%; }")
        self._context.storage_state(path=SESSION_FILE)

        self.logged_in = True

    def _enter_credentials(self, username: str, password: str) -> None:
        page = self.page
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("#password").press("Enter")
        logger.info("Credentials entered")

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
