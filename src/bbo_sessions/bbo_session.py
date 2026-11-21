import re
from datetime import datetime, time, timedelta

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bbo_sessions import logger
from bbo_sessions.bbo_phoenix import BboPhoenixSession
from bbo_sessions.config import config
from bbo_sessions.models import Tournament

SESSION_PATTERN = re.compile(r"#(\d+)\s+.*?\b(\d{1,2} [A-Za-z]+ \d{4})\b")
EXTRA_MINUTES = 2

DELETE_DATES = [
    datetime(2026, 11, 30).date(),
    datetime(2026, 12, 2).date(),
    datetime(2026, 12, 3).date(),
]


class BboSession(BboPhoenixSession):
    """Own the browser so it stays open between button clicks."""

    def __init__(self, headless: bool = True) -> None:
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
            logger.info(f"Modified tournament {when}")

        self.close()

    def get_current_tournaments(self) -> list[str]:
        self.login()
        page = self.page
        page.locator('mat-icon[data-mat-icon-name="director"]').click()
        page.get_by_role("tab", name="Pending Tournaments").click()
        return self._get_tournament_dates()

    def _get_tournament_dates(self, timeout: int = 15000) -> list[datetime]:
        """Return the start of every 'Starts: ...' entry as a datetime."""
        page = self.page
        page.wait_for_function(
            "(pattern) => new RegExp(pattern).test(document.body.innerText)",
            arg=SESSION_PATTERN.pattern,
            timeout=timeout,
        )
        text = page.locator("body").inner_text()
        found = []
        for match in SESSION_PATTERN.finditer(text):
            try:
                when = datetime.strptime(match.group(2), "%d %B %Y").date()
            except ValueError:
                continue
            found.append(Tournament(number=match.group(1), date=when))
        logger.info(f"Found {len(found)} tournament dates")
        return found

    def create_new_tournaments(
        self,
        existing_tournaments: list[Tournament],
        new_tournaments: list[Tournament],
    ) -> None:
        """Create new tournaments for the given tournament dates."""
        try:
            for existing, new in zip(
                existing_tournaments, new_tournaments, strict=True
            ):
                self._create_tournament(existing, new)
        except Exception as e:
            logger.error(f"Error creating tournaments: {e}")
            return "ERROR"
        finally:
            self.close()
        return "OK"

    def _create_tournament(self, existing_tournament, new_tournament) -> None:
        page = self.page

        existing_tournament_text = (
            f"{existing_tournament.number} Phoenix Bridge Club "
            f"{existing_tournament.date.strftime('%d')}"
        )

        self._click_on_tournament(existing_tournament_text)
        page.get_by_text("Edit Tournament").click(timeout=500)
        page.get_by_role("button", name="Copy tournament").click(timeout=5000)

        self._update_title()
        self._update_date(new_tournament)

        # Modify  the tournament
        modify_btn = page.get_by_role("button", name="Modify tournament")
        modify_btn.wait_for(state="visible", timeout=5000)
        modify_btn.click(timeout=500)

        # Close the updated tournament properties popup
        popup = page.locator("tournament-properties-popup")
        popup.get_by_role("button", name="Close").click()

        logger.info(
            "Tournament created",
            extra={"Created for": new_tournament.date.strftime("%Y-%m-%d")},
        )

    def _click_on_tournament(self, tournament_text: str) -> None:
        page = self.page
        link = page.get_by_text(tournament_text)
        count = link.count()

        if count == 0:
            # Show what is on the page that looks similar
            first_word = str(tournament_text).split()[0]
            similar = page.get_by_text(
                re.compile(re.escape(first_word), re.IGNORECASE)
            )
            logger.warning(
                "Nothing matches. Similar text: %s",
                [t.strip()[:80] for t in similar.all_inner_texts()][:10],
            )
            raise RuntimeError(
                f"Tournament link not found: {tournament_text!r}"
            )

        try:
            link.first.click(timeout=10000)
        except PlaywrightTimeoutError as error:
            logger.error("Click failed: %s", str(error)[:600])
            raise

    def _update_title(self) -> None:
        page = self.page
        # page.pause()
        title_field = page.get_by_role("textbox", name="Title")
        title_field.wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(1000)  # Essential to get number in title

        title = title_field.input_value().strip()
        updated_title = self._get_new_title(title)
        title_field.fill(updated_title)

    def _update_date(self, new_tournament: Tournament) -> None:
        # Date and time
        page = self.page
        days, hours, minutes = self._get_time(new_tournament.date)

        day_btn = page.get_by_role("spinbutton", name="D")
        hour_btn = page.get_by_role("spinbutton", name="H")
        minute_btn = page.get_by_role("spinbutton", name="M")

        day_btn.fill(str(days))
        hour_btn.fill(str(hours))
        minute_btn.fill(str(minutes + EXTRA_MINUTES))

    def _get_time(self, tournament_date) -> tuple[str]:
        days = (tournament_date - datetime.now().date()).days
        now = datetime.now()
        target = datetime.combine(
            now.date(), time(config.start_hour, config.start_minute)
        )
        delta = target - now
        total_minutes = int(delta.total_seconds() // 60)
        return days, *divmod(total_minutes, 60)

    def _get_new_title(self, title: str) -> str:
        """Update the title field with the new title."""
        new_date = self._get_new_date(title)
        tournament_number = self._get_tournament_number(title)

        # Build the result
        return (
            f"#{tournament_number} {config.club_name} "
            f"{new_date.strftime('%d %B %Y')}"
        )

    def _get_new_date(self, title: str) -> datetime:
        # Extract the date from the captured title
        date_match = re.search(r"\d{1,2} \w+ \d{4}", title)
        if not date_match:
            logger.error("Date not found in captured title: %s", title)
            raise ValueError("Date not found in captured title")

        captured_date = datetime.strptime(date_match.group(), "%d %B %Y")
        return captured_date + timedelta(days=7)

    def _get_tournament_number(self, title: str) -> str:
        """Extract the tournament number from the title."""
        number_match = re.match(r"#(\d+)", title)
        if not number_match:
            logger.error("Tournament number not found in new title: %s", title)
            raise ValueError("Tournament number not found in new title")
        return number_match.group(1)

    def cron_create_tournaments(self) -> None:
        """Create tournaments for the next week."""
        self.login()
        existing_tournaments = self.get_current_tournaments()
        new_tournaments = get_new_tournaments(existing_tournaments)
        return self.create_new_tournaments(
            existing_tournaments, new_tournaments
        )

    def delete_tournaments(self):
        """Delete tournaments for dates in DELETE_DATES."""
        self.login()
        existing_tournaments = self.get_current_tournaments()

        tournaments_to_delete = [
            tournament
            for tournament in existing_tournaments
            if tournament.date in DELETE_DATES
        ]

        page = self.page

        for tournament in tournaments_to_delete:
            existing_tournament_text = (
                f"{tournament.number} Phoenix Bridge Club "
                f"{tournament.date.strftime('%d')}"
            )
            self._click_on_tournament(existing_tournament_text)
            page.get_by_text("Destroy Tournament").click(timeout=500)
            page.get_by_role(
                "checkbox", name="I confirm I want to cancel #"
            ).check()
            page.get_by_role("button", name="Destroy Tournament").click()
            logger.info(f"Deleted tournament {tournament.date}")
        return "OK"


def get_new_tournaments(
    existing_tournaments: list[Tournament],
) -> list[datetime]:
    """Get the new tournaments."""
    cutoff = (datetime.today() + timedelta(days=14)).date()
    existing_dates = {tournament.date for tournament in existing_tournaments}

    new_tournaments = []
    for tournament in existing_tournaments:
        new_start = tournament.date + timedelta(days=7)
        if tournament.date <= cutoff and new_start not in existing_dates:
            new_tournaments.append(Tournament(tournament.number, new_start))
            existing_dates.add(new_start)  # avoid duplicates

    return new_tournaments
