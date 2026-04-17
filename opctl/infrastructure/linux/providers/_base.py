import subprocess
from typing import List
from opctl.infrastructure.validators import (
    validate_hostname, validate_mac, validate_ip,
    validate_dns, validate_interface, validate_port,
)


class LinuxProvider:
    validate_hostname = staticmethod(validate_hostname)
    validate_mac = staticmethod(validate_mac)
    validate_ip = staticmethod(validate_ip)
    validate_dns = staticmethod(validate_dns)
    validate_interface = staticmethod(validate_interface)
    validate_port = staticmethod(validate_port)

    def _run(self, cmd: List[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"Command error: {error_msg}\nCommand: {' '.join(cmd)}")
