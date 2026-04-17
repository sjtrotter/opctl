import shutil
import socket
from opctl.domain.interfaces import ISystemAdapter, IProvider
from .._base import WindowsProvider


class WmicSystemProvider(WindowsProvider, ISystemAdapter, IProvider):
    """Legacy fallback using WMIC (deprecated in Windows 11 but present on older systems)."""

    @classmethod
    def provider_name(cls) -> str:
        return "wmic"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("wmic") is not None

    def set_hostname(self, hostname: str) -> None:
        current = socket.gethostname()
        self._run_cmd(
            f'wmic computersystem where name="{current}" call rename name="{hostname}"'
        )

    def get_hostname(self) -> str:
        return socket.gethostname()
