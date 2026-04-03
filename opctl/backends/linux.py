import subprocess
from .base import NetworkBackend

class LinuxBackend(NetworkBackend):
    def _run(self, cmd):
        """Internal helper to execute shell commands securely."""
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def get_hostname(self):
        return self._run(["hostname"])

    def set_hostname(self, hostname):
        # Uses hostnamectl as planned for RHEL-independent setup
        return self._run(["sudo", "hostnamectl", "set-hostname", hostname])

    def get_hwaddress(self, iface="enp2s0"):
        # Ported from your original ip link/grep logic
        output = self._run(["ip", "link", "show", iface])
        for line in output.split('\n'):
            if "link/ether" in line:
                return line.split()[1]
        return None

    def set_fw_rule(self, ip_address, action="allow"):
        """Implements firewall-cmd logic for Fedora/RHEL."""
        cmd = ["sudo", "firewall-cmd", "--permanent"]
        if action == "allow":
            cmd.append(f"--add-source={ip_address}")
        
        self._run(cmd)
        return self._run(["sudo", "firewall-cmd", "--reload"])