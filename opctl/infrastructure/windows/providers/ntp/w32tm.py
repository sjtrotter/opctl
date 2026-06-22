import shutil
from typing import List
from opctl.domain.interfaces import INtpAdapter, IProvider
from .._base import WindowsProvider

_NTP_REG = r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters"


class W32tmProvider(WindowsProvider, INtpAdapter, IProvider):
    """Windows Time service (w32tm). /manualpeerlist overwrites, so it's idempotent."""

    @classmethod
    def provider_name(cls) -> str:
        return "w32tm"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("w32tm") is not None

    def set_servers(self, servers: List[str], enabled: bool) -> None:
        # _run_cmd is string-based (shell=True), so validating every server is the
        # load-bearing guard against command-line injection.
        for s in servers:
            self.validate_ntp_server(s)

        if not enabled:
            # Least-destructive disable: stop syncing from the manual list without
            # unregistering the service or wiping its config.
            self._run_cmd("w32tm /config /syncfromflags:NO /update")
            return

        peers = " ".join(f"{s},0x8" for s in servers)
        self._run_cmd(
            f'w32tm /config /manualpeerlist:"{peers}" /syncfromflags:manual /update')
        self._run_cmd("w32tm /resync /rediscover /nowait")

    def get_servers(self) -> List[str]:
        try:
            out = self._run_cmd(f'reg query "{_NTP_REG}" /v NtpServer')
        except RuntimeError:
            return []
        for line in out.splitlines():
            if "NtpServer" in line and "REG_SZ" in line:
                value = line.split("REG_SZ", 1)[1].strip()
                # strip the ,0xNN flags from each entry
                return [tok.split(",")[0] for tok in value.split() if tok]
        return []
