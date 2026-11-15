import subprocess
import sys

from playwright.sync_api import Error as PlaywrightError


def launch_chromium(playwright, headless: bool = False):
    """Launch Chromium, downloading the matching build if it is missing."""
    try:
        return playwright.chromium.launch(headless=headless)
    except PlaywrightError as error:
        if "playwright install" not in str(error):
            raise
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
        return playwright.chromium.launch(headless=headless)
