# forms/frm_main.py

"""AppFrame for BBO Sessions."""

import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from dotenv import load_dotenv
from psiutils.constants import PAD
from psiutils.utilities import window_resize

from bbo_sessions.bbo_session import BboSession
from bbo_sessions.buttons import ButtonFrame, IconButton
from bbo_sessions.config import config
from bbo_sessions.constants import APP_TITLE
from bbo_sessions.main_menu import MainMenu
from bbo_sessions.state import state
from bbo_sessions.text import Text

txt = Text()
DATES = [
    datetime(2026, 10, 22, 19, 20),
    datetime(2026, 10, 26, 20, 20),
    datetime(2026, 10, 28, 20, 20),
    datetime(2026, 10, 29, 20, 20),
]
GET_FROM_BBO = True


class AppFrame:
    """Create AppFrame for BBO Sessions application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.existing_sessions = (  # <class 'datetime.date'>
            self._get_existing_sessions()
        )
        self.new_sessions = (  # <class 'datetime.date'>
            self._get_new_sessions()
        )

        self._show()

        self._poulate_new_sessions(self.new_sessions_frame)
        self._verify_sessions()

    def _show(self):
        root = self.root
        root.geometry(state.get_geometry(__file__))
        root.title(APP_TITLE)

        main_menu = MainMenu(self)
        main_menu.create()

        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        main_frame = self._main_frame(root)
        main_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=PAD, pady=PAD)

        self.button_frame = self._button_frame(root)
        self.button_frame.grid(
            row=8, column=0, columnspan=9, sticky=tk.EW, padx=PAD, pady=PAD
        )

        sizegrip = ttk.Sizegrip(root)
        sizegrip.grid(column=0, sticky=tk.SE)

        root.update_idletasks()
        root.bind("<Control-x>", self._dismiss)
        root.bind("<Control-o>", self._process)
        root.bind(
            "<Configure>",
            lambda e: window_resize(root, __file__, state),
        )

    def _main_frame(self, master: tk.Frame) -> ttk.Frame:
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=1)

        row = 0
        existing_sessions_frame = self._existing_sessions_frame(frame)
        existing_sessions_frame.grid(
            row=row, column=0, sticky=tk.NSEW, padx=PAD, pady=PAD
        )
        self.new_sessions_frame = self._new_sessions_frame(frame)
        self.new_sessions_frame.grid(
            row=row, column=1, sticky=tk.NSEW, padx=PAD, pady=PAD
        )

        return frame

    def _existing_sessions_frame(self, master: tk.Frame) -> ttk.Frame:
        frame = ttk.Frame(master)

        row = 0
        label = ttk.Label(frame, text="Existing Sessions")
        label.grid(row=row, column=0, sticky=tk.W, padx=PAD)
        row += 1
        label = ttk.Label(frame, text="=================")
        label.grid(row=row, column=0, sticky=tk.W, padx=PAD)

        for row, session in enumerate(self.existing_sessions):
            existing = ttk.Label(frame, text=session.strftime("%d %b %Y (%A)"))
            existing.grid(row=row + 2, column=0, sticky=tk.W, padx=PAD)

        return frame

    def _new_sessions_frame(self, master: tk.Frame) -> ttk.Frame:
        frame = ttk.Frame(master)

        return frame

    def _button_frame(self, master: tk.Frame) -> tk.Frame:
        frame = ButtonFrame(master, tk.HORIZONTAL)
        frame.buttons = self._frame_buttons(frame)
        frame.disable()
        return frame

    def _frame_buttons(self, frame: ButtonFrame) -> list[IconButton]:
        return [
            frame.icon_button("build", self._process),
            frame.icon_button("cancel", self._dismiss),
        ]

    def _get_existing_sessions(self) -> list[datetime]:
        """Get the existing sessions."""
        if GET_FROM_BBO:
            load_dotenv()
            self.session: BboSession | None = BboSession()
            self.session.login(
                os.environ["BBO_USERNAME"], os.environ["BBO_PASSWORD"]
            )
            current_sessions = self.session.get_current_sessions()
            return [
                date
                for date in current_sessions
                if date > datetime.now().date()
            ]

        return [
            date.date()
            for date in DATES
            if date.date() > datetime.now().date()
        ]

    def _get_new_sessions(self) -> list[datetime]:
        """Get the new sessions."""
        cutoff = (datetime.today() + timedelta(days=14)).date()
        existing_dates = {d for d in self.existing_sessions}

        new_sessions = []
        for start in self.existing_sessions:
            new_start = start + timedelta(days=7)
            if start <= cutoff and new_start not in existing_dates:
                new_sessions.append(new_start)
                existing_dates.add(new_start)  # avoid duplicates

        return new_sessions

    def _poulate_new_sessions(self, frame: tk.Frame) -> None:
        """Populate the new sessions."""
        for widget in self.new_sessions_frame.winfo_children():
            widget.destroy()

        row = 0
        label = ttk.Label(frame, text="New Sessions")
        label.grid(row=row, column=0, sticky=tk.W)
        row += 1
        label = ttk.Label(frame, text="=============")
        label.grid(row=row, column=0, sticky=tk.W)

        for row, session in enumerate(self.new_sessions):
            new = ttk.Label(frame, text=session.strftime("%d %b %Y (%A)"))
            new.grid(row=row + 2, column=0, sticky=tk.W)

    def _verify_sessions(self):
        """Verify that the sessions are valid."""
        errors = []
        weekdays = {0: 0, 2: 0, 3: 0}
        days = {0: "Monday", 2: "Wednesday", 3: "Thursday"}
        if len(self.existing_sessions) != 3:
            errors.append("Invalid number of sessions")

        for session in self.existing_sessions:
            weekday = session.weekday()
            if weekday in (0, 2, 3):
                weekdays[weekday] += 1
            else:
                errors.append(
                    f"{session.strftime('%d %b %Y (%A)')} "
                    f"is not a Monday, Wednesday, or Thursday"
                )

        for weekday, count in weekdays.items():
            if count != 1:
                errors.append(f"{days[weekday]} has {count} entries")

        if errors:
            messagebox.showerror("Invalid Sessions", "\n".join(errors))
            return False

        return True

    def _value_changed(self, *args) -> bool:
        """
        Determine whether any configuration value has changed.
        """
        enable = self.xxx.get() != config.xxx
        self.button_frame.enable(enable)

    def _process(self, *args) -> None:
        if not GET_FROM_BBO:
            self._debug_dates()
            return
        process = self.session.create_new_tournaments(
            self.existing_sessions, self.new_sessions
        )
        if process == "OK":
            messagebox.showinfo("Success", "Process completed successfully")
        else:
            messagebox.showerror("Error", "Process failed")
        self._dismiss()

    def _debug_dates(self) -> None:
        print(f"GET_FROM_BBO {GET_FROM_BBO}")
        from datetime import time

        for session in self.new_sessions:
            print((session - datetime.now().date()).days)
            days = (session - datetime.now().date()).days
            print(days)

        now = datetime.now()
        target = datetime.combine(now.date(), time(19, 20))

        delta = target - now
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)

        print(f"{hours}h {minutes}m")

    def _dismiss(self, *args) -> None:
        self.root.destroy()
