import shutil
import socket
from opctl.domain.interfaces import ISystemAdapter, IProvider
from .._base import LinuxProvider


class HostnamectlProvider(LinuxProvider, ISystemAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "hostnamectl"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("hostnamectl") is not None

    def set_hostname(self, hostname: str) -> None:
        self.validate_hostname(hostname)
        self._run(["hostnamectl", "set-hostname", hostname])

    def get_hostname(self) -> str:
        return socket.gethostname()
