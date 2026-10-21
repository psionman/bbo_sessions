import re
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bbo_sessions.constants import DATE_DISPLAY_FORMAT

LOGIN_URL = "https://www.bridgebase.com/v3/auth/login"
SESSION_FILE = Path("bbo_session.json")


STARTS_PATTERN = re.compile(
    r"Starts:\s*(\w{3}, \d{1,2} \w{3} \d{4}, \d{1,2}:\d{2})"
)

COOKIE_BUTTON = re.compile(r"accept|agree|allow", re.IGNORECASE)
COOKIE_TIMEOUT = 1000


def accept_cookies(page: Page) -> None:
    """Click the cookie consent button if one appears."""
    button = page.get_by_role("button", name=COOKIE_BUTTON).first
    try:
        button.click(timeout=COOKIE_TIMEOUT)
    except PlaywrightTimeoutError:
        pass  # No banner this time


def get_session_dates(page: Page, timeout: int = 15000) -> list[datetime]:
    """Return the start of every 'Starts: ...' entry as a datetime."""
    page.wait_for_function(
        "(pattern) => new RegExp(pattern).test(document.body.innerText)",
        arg=STARTS_PATTERN.pattern,
        timeout=timeout,
    )
    text = page.locator("body").inner_text()

    return [
        datetime.strptime(match, DATE_DISPLAY_FORMAT)
        for match in STARTS_PATTERN.findall(text)
    ]


class BboSession:
    """Own the browser so it stays open between button clicks."""

    def __init__(self, headless: bool = False) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._context = self._browser.new_context()
        self.page: Page = self._context.new_page()

    def login(self, username: str, password: str) -> None:
        page = self.page
        page.goto(LOGIN_URL)
        accept_cookies(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("#password").press("Enter")
        page.wait_for_url(lambda url: "/auth/login" not in url)
        self._context.storage_state(path=SESSION_FILE)

    def get_pending_sessions(self) -> list[str]:
        page = self.page
        page.locator('mat-icon[data-mat-icon-name="director"]').click()
        page.get_by_role("tab", name="Pending Tournaments").click()
        return get_session_dates(page)

    def process(self, starts: list[str]) -> None:
        """Carry on with the chosen entry."""
        for start in starts:
            self._create_tournament(start.strftime(DATE_DISPLAY_FORMAT))

    def _create_tournament(self, date) -> None:
        page = self.page

        tournament = page.locator(".itemClass").filter(
            has_text=date[0] if isinstance(date, list) else date
        )

        # Click on tournament
        tournament.click()

        page.wait_for_timeout(500)

        # Click on menu
        edit_item = (
            page.locator("menu-item")
            .filter(has=page.locator("div").filter(has_text="Edit Tournament"))
            .filter(has_text="Edit Tournament")
        )

        edit_item.click()

        page.wait_for_timeout(500)
        # -------------------------------------------------
        # Get the Title value before copying
        # -------------------------------------------------
        title_field = page.get_by_role("textbox", name="Title")
        title_field.wait_for(state="visible", timeout=5000)

        source_title = title_field.input_value().strip()
        print(
            f"Captured title: {source_title}"
        )  # e.g. "#64520 Phoenix Bridge Club 21 October 2026"

        page.wait_for_timeout(500)
        # -------------------------------------------------
        # Click the Copy tournament button
        # -------------------------------------------------
        copy_btn = page.get_by_role("button", name="Copy tournament")
        copy_btn.wait_for(state="visible", timeout=5000)
        copy_btn.click()

        page.wait_for_timeout(500)
        # -------------------------------------------------
        # Fill the title with the copied title
        # -------------------------------------------------
        new_title = title_field.input_value().strip()
        print(f"New title: {new_title}")

        title_field.fill(self._update_title(page, source_title, source_title))

        # Date and time
        day_btn = page.get_by_role("spinbutton", name="D")
        source_day = day_btn.input_value().strip()
        day_btn.fill(str(int(source_day) + 7))

        # Modify  the tournament
        modify_btn = page.get_by_role("button", name="Modify tournament")
        modify_btn.wait_for(state="visible", timeout=5000)
        modify_btn.click()

        # page.pause()
        self.close()
        return True

    def _update_title(self, page, source_title: str, new_title: str) -> str:
        """Update the title field with the new title."""
        # Extract the date from the captured title
        date_match = re.search(r"\d{1,2} \w+ \d{4}", source_title)
        if not date_match:
            raise ValueError("Date not found in captured title")

        captured_date = datetime.strptime(date_match.group(), "%d %B %Y")
        new_date = captured_date + timedelta(days=7)

        # Extract the club number from the new title
        number_match = re.match(r"#(\d+)", new_title)
        if not number_match:
            raise ValueError("Club number not found in new title")

        tournament_number = number_match.group(1)

        # Extract the club name from the captured title
        club_name = re.sub(r"^#\d+\s*", "", source_title)
        club_name = re.sub(r"\s+\d{1,2} \w+ \d{4}$", "", club_name)

        # Build the result
        return (
            f"#{tournament_number} {club_name} {new_date.strftime('%d %B %Y')}"
        )

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()
