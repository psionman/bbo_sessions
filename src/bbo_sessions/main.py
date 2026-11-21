# main.py

"""
A tkinter application for BBO Sessions.
"""

import os
import sys
import tkinter as tk

from dotenv import load_dotenv
from forms.frm_main import AppFrame
from psiutils.utilities import display_icon
from psiutils.widgets import get_styles

from bbo_sessions import __app_name__, __version__
from bbo_sessions.bbo_session import BboSession
from bbo_sessions.constants import APP_TITLE, ICON_FILE
from bbo_sessions.module_caller import ModuleCaller

load_dotenv()
uv_python = os.getenv("UV_PYTHON")


PARSER_ARGS = (
    ("module", "Module to load"),
    ("project", "Project name"),
    ("secondary", "Secondary argument"),
)


def main() -> None:
    root = tk.Tk()
    root.title(APP_TITLE)
    display_icon(root, ICON_FILE, ignore_error=True)

    root.protocol("WM_DELETE_WINDOW", root.destroy)

    get_styles()

    if PARSER_ARGS:
        args = ModuleCaller.create_parser(PARSER_ARGS)
        if args.module:
            try:
                ModuleCaller(root, args)
            except Exception:
                root.destroy()
        else:
            AppFrame(root)

    root.mainloop()


if __name__ == "__main__":
    if "create_tournaments" in sys.argv:
        BboSession(True).cron_create_tournaments()
        sys.exit(0)
    if "delete_tournaments" in sys.argv:
        BboSession(True).delete_tournaments()
        sys.exit(0)
    if "--version" in sys.argv:
        print(f"{__app_name__}. Version: {__version__}")
        sys.exit(0)
    main()
