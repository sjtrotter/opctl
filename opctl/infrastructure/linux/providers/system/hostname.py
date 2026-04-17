import shutil
import socket
from opctl.domain.interfaces import ISystemAdapter, IProvider
from .._base import LinuxProvider


class HostnameProvider(LinuxProvider, ISystemAdapter, IProvider):
    """Legacy fallback using the hostname command and /etc/hostname."""

    @classmethod
    def provider_name(cls) -> str:
        return "hostname"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("hostname") is not None

    def set_hostname(self, hostname: str) -> None:
        self.validate_hostname(hostname)
        self._run(["hostname", hostname])
        try:
            with open("/etc/hostname", "w") as f:
                f.write(hostname + "\n")
        except PermissionError:
            pass

    def get_hostname(self) -> str:
        return socket.gethostname()
