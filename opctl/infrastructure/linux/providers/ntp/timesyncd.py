import os
import shutil
from typing import List
from opctl.domain.interfaces import INtpAdapter, IProvider
from .._base import LinuxProvider
from .chrony import ChronyProvider

_CONF_DIR = "/etc/systemd/timesyncd.conf.d"
_CONF_FILE = _CONF_DIR + "/90-opctl.conf"


class TimesyncdProvider(LinuxProvider, INtpAdapter, IProvider):
    """systemd-timesyncd. Owns a single drop-in so the vendor config is never touched."""

    @classmethod
    def provider_name(cls) -> str:
        return "timesyncd"

    @classmethod
    def is_available(cls) -> bool:
        # The complement of chrony's selection: timesyncd covers any systemd host
        # where chrony is NOT the resolvable daemon. (Gating on chrony.is_available()
        # rather than mere chronyc presence avoids a dead zone where chronyc exists
        # but chronyd doesn't — there, neither would match.)
        return shutil.which("timedatectl") is not None and not ChronyProvider.is_available()

    def set_servers(self, servers: List[str], enabled: bool) -> None:
        for s in servers:
            self.validate_ntp_server(s)
        os.makedirs(_CONF_DIR, mode=0o755, exist_ok=True)
        # The bare `NTP=` reset is mandatory: NTP= is a list option that systemd
        # COLLECTS across files, so the empty assignment clears prior entries and
        # makes our line the entire effective list.
        content = (
            "# Managed by opctl. Do not edit by hand.\n"
            "[Time]\n"
            "NTP=\n"
            f"NTP={' '.join(servers)}\n"
        )
        self._atomic_write(_CONF_FILE, content)
        if enabled:
            self._run(["timedatectl", "set-ntp", "true"])
            # No live reload — restart so the daemon re-reads the drop-in.
            self._run(["systemctl", "restart", "systemd-timesyncd"])
        else:
            self._run(["timedatectl", "set-ntp", "false"])

    def get_servers(self) -> List[str]:
        try:
            out = self._run(["timedatectl", "show-timesync",
                             "--property=SystemNTPServers", "--value"])
            return out.split() if out else []
        except RuntimeError:
            return []
