# module_caller.py
"""Module caller for BBO Sessions."""

from psiutils.module_caller import ModuleCaller as ModuleCallerBase

from bbo_tournaments.bbo_session import BboSession
from bbo_tournaments.forms.frm_config import ConfigFrame


class ModuleCaller(ModuleCallerBase):
    def __init__(self, root, parsed_args: dict) -> None:
        self.modules = {
            "config": (self._config, None),
            "cron": (self._cron, None),
            # "delete_tournaments": (self.delete_tournaments, None),
            # "create_tournaments": (self._create_tournaments, None),
            "email": (self.send_email, None),
        }
        super().__init__(root, parsed_args)

    def _config(self) -> None:
        print("Calling... config")
        dlg = ConfigFrame(self)
        self.root.wait_window(dlg.root)

    def _cron(self) -> None:
        print("Calling... cron")
        result = BboSession(True).cron_create_tournaments()
        print(f"Cron result: {result}")

    def delete_tournaments(self) -> None:
        print("Calling... delete tournaments")
        result = BboSession(True).delete_tournaments()
        print(f"Delete result: {result}")

    def _create_tournaments(self) -> None:
        print("Calling... create tournaments")
        BboSession(True).cron_create_tournaments()

    def send_email(self) -> None:
        print("Calling... send email")
        from bbo_tournaments.emails import send

        response = send()
        print(f"Email result: {response}")
