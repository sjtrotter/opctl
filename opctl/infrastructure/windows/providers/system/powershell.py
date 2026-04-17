import shutil
import socket
from opctl.domain.interfaces import ISystemAdapter, IProvider
from .._base import WindowsProvider


class PowerShellSystemProvider(WindowsProvider, ISystemAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "powershell"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("powershell") is not None

    def set_hostname(self, hostname: str) -> None:
        self._run_ps(f'Rename-Computer -NewName "{hostname}" -Force')

    def get_hostname(self) -> str:
        return socket.gethostname()
