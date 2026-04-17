import subprocess
from opctl.infrastructure.validators import (
    validate_hostname, validate_mac, validate_ip,
    validate_dns, validate_interface, validate_port,
)


class WindowsProvider:
    # Re-export validators so subclasses can call self.validate_*
    validate_hostname = staticmethod(validate_hostname)
    validate_mac = staticmethod(validate_mac)
    validate_ip = staticmethod(validate_ip)
    validate_dns = staticmethod(validate_dns)
    validate_interface = staticmethod(validate_interface)
    validate_port = staticmethod(validate_port)

    def _run_ps(self, cmd: str) -> str:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"PowerShell error: {error_msg}\nCommand: {cmd}")

    def _run_cmd(self, cmd: str) -> str:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"CMD error: {error_msg}\nCommand: {cmd}")
