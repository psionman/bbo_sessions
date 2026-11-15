import re
from datetime import datetime, time, timedelta

from bbo_sessions.bbo_phoenix import BboPhoenixSession
from bbo_sessions.config import config
from bbo_sessions.models import Session

SESSION_PATTERN = re.compile(r"#(\d+)\s+.*?\b(\d{1,2} [A-Za-z]+ \d{4})\b")
EXTRA_MINUTES = 2


class BboSession(BboPhoenixSession):
    """Own the browser so it stays open between button clicks."""

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

    def modify_tournaments(self, timeout: int = 15000) -> None:
        """Modify existing tournaments."""
        self._login()

        page = self.page
        page.wait_for_function(
            "(pattern) => new RegExp(pattern).test(document.body.innerText)",
            arg=SESSION_PATTERN.pattern,
            timeout=timeout,
        )
        text = page.locator("body").inner_text()

        for match in SESSION_PATTERN.finditer(text):
            try:
                when = datetime.strptime(match.group(2), "%d %B %Y").date()
            except ValueError:
                continue

            tournament_text = match.group(0)

            # Open tournament menu
            page.get_by_text(tournament_text, exact=False).first.click()

            # Select Edit Tournament
            page.get_by_text("Edit Tournament", exact=True).click()

            # Modify tournament
            page.get_by_role("button", name="Modify tournament").click()

            # Close tournament properties popup
            page.locator("tournament-properties-popup").get_by_role(
                "button", name="Close"
            ).click()
            print(f"Modified tournament {when}")

        self.close()

    def create_new_tournaments(
        self,
        existing_sessions: list[Session],
        new_sessions: list[Session],
    ) -> None:
        """Create new tournaments for the given session dates."""
        try:
            for existing, new in zip(
                existing_sessions, new_sessions, strict=True
            ):
                self._create_tournament(existing, new)
        except Exception as e:
            print(f"Error creating tournaments: {e}")
            return "ERROR"
        finally:
            self.close()
        return "OK"

    def _create_tournament(self, existing_session_date, new_session) -> None:
        page = self.page

        existing_session_text = (
            f"#{existing_session_date.number} Phoenix Bridge Club "
            f"{existing_session_date.date.strftime('%d')}"
        )

        page.get_by_text(existing_session_text).click()
        page.get_by_text("Edit Tournament").click()

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
        title_field = page.get_by_role("textbox", name="Title")
        title_field.wait_for(state="visible", timeout=5000)

        source_title = title_field.input_value().strip()
        updated_title = self._update_title(page, source_title, source_title)
        title_field.fill(updated_title)

        # Date and time
        days, hours, minutes = self._get_time(new_session.date)

        day_btn = page.get_by_role("spinbutton", name="D")
        hour_btn = page.get_by_role("spinbutton", name="H")
        minute_btn = page.get_by_role("spinbutton", name="M")

        day_btn.fill(str(days))
        hour_btn.fill(str(hours))
        minute_btn.fill(str(minutes + EXTRA_MINUTES))

        # Modify  the tournament
        modify_btn = page.get_by_role("button", name="Modify tournament")
        modify_btn.wait_for(state="visible", timeout=5000)
        modify_btn.click()

        # Close the updated tournament properties popup
        page.wait_for_timeout(500)
        popup = page.locator("tournament-properties-popup")
        popup.get_by_role("button", name="Close").click()

    def _get_time(self, session_date) -> tuple[str]:
        days = (session_date - datetime.now().date()).days
        now = datetime.now()
        target = datetime.combine(
            now.date(), time(config.start_hour, config.start_minute)
        )
        delta = target - now
        total_minutes = int(delta.total_seconds() // 60)
        return days, *divmod(total_minutes, 60)

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
            raise ValueError("Tournament number not found in new title")

        tournament_number = number_match.group(1)

        # Build the result
        return (
            f"#{tournament_number} {config.club_name} "
            f"{new_date.strftime('%d %B %Y')}"
        )
