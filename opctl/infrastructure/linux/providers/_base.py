import os
import subprocess
import tempfile
from typing import List
from opctl.domain.services.validators import (
    validate_hostname, validate_mac, validate_ip,
    validate_dns, validate_interface, validate_port, validate_ntp_server,
)


class LinuxProvider:
    validate_hostname = staticmethod(validate_hostname)
    validate_mac = staticmethod(validate_mac)
    validate_ip = staticmethod(validate_ip)
    validate_dns = staticmethod(validate_dns)
    validate_interface = staticmethod(validate_interface)
    validate_port = staticmethod(validate_port)
    validate_ntp_server = staticmethod(validate_ntp_server)

    def _run(self, cmd: List[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"Command error: {error_msg}\nCommand: {' '.join(cmd)}")

    def _atomic_write(self, path: str, content: str, mode: int = 0o644) -> None:
        """Write a config file via temp-in-same-dir + rename, so a reader never
        sees a half-written file."""
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".opctl-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
