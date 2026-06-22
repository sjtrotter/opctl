import os
import shutil
from typing import List
from opctl.domain.interfaces import INtpAdapter, IProvider
from .._base import LinuxProvider

_CHRONY_CONF = "/etc/chrony.conf"
_SOURCES_DIR = "/etc/chrony/sources.d"
_SOURCES_FILE = _SOURCES_DIR + "/opctl.sources"
_SOURCEDIR_LINE = f"sourcedir {_SOURCES_DIR}"


class ChronyProvider(LinuxProvider, INtpAdapter, IProvider):
    """chrony / chronyd. Writes a dedicated `.sources` drop-in and hot-reloads it.

    chrony reads source directives from a `sourcedir`; if the host config doesn't
    already point at a persistent one, we append a single `sourcedir` line to
    chrony.conf (idempotent) — that requires one restart, after which changes
    hot-reload via `chronyc reload sources` with no restart.
    """

    @classmethod
    def provider_name(cls) -> str:
        return "chrony"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("chronyc") is not None and shutil.which("chronyd") is not None

    def set_servers(self, servers: List[str], enabled: bool) -> None:
        for s in servers:
            self.validate_ntp_server(s)
        os.makedirs(_SOURCES_DIR, mode=0o755, exist_ok=True)
        just_wired = self._ensure_sourcedir()

        content = "# Managed by opctl - do not edit\n" + "".join(
            f"server {s} iburst\n" for s in servers)
        self._atomic_write(_SOURCES_FILE, content)

        self._run(["timedatectl", "set-ntp", "true" if enabled else "false"])
        if not enabled:
            return
        if just_wired:
            # `sourcedir` is read only at startup — restart once to pick it up.
            self._run(["systemctl", "restart", "chronyd"])
        else:
            try:
                self._run(["chronyc", "reload", "sources"])
            except RuntimeError:
                self._run(["systemctl", "restart", "chronyd"])

    def get_servers(self) -> List[str]:
        # Read the tool-owned file (the authoritative record of what we set), not
        # `chronyc sources`, which also lists DHCP/vendor sources we must not touch.
        try:
            with open(_SOURCES_FILE) as f:
                return [parts[1] for parts in (ln.split() for ln in f)
                        if len(parts) >= 2 and parts[0] in ("server", "pool", "peer")]
        except FileNotFoundError:
            return []

    def _ensure_sourcedir(self) -> bool:
        """Append our sourcedir to chrony.conf if absent. Returns True if it was added."""
        try:
            with open(_CHRONY_CONF) as f:
                conf = f.read()
        except FileNotFoundError:
            conf = ""
        if any(line.strip() == _SOURCEDIR_LINE for line in conf.splitlines()):
            return False
        with open(_CHRONY_CONF, "a") as f:
            f.write(f"\n# Added by opctl\n{_SOURCEDIR_LINE}\n")
        return True
