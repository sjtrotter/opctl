import subprocess
from .base import NetworkBackend

class WindowsBackend(NetworkBackend):
    def _run_ps(self, cmd_string):
        """Internal helper to execute PowerShell commands."""
        # We use -ExecutionPolicy Bypass to ensure scripts run in restricted environments
        full_cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_string]
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def get_hostname(self):
        # Uses the built-in environment variable for speed
        return self._run_ps("$env:COMPUTERNAME")

    def set_hostname(self, hostname):
        """
        Sets the hostname using Rename-Computer.
        Note: Windows requires a restart for this to take full effect.
        """
        # Ported from your original 'wmic' idea but using modern PowerShell
        cmd = f"Rename-Computer -NewName '{hostname}' -Force"
        return self._run_ps(cmd)

    def get_hwaddress(self, iface=None):
        """
        Returns the MAC address. 
        If no iface is provided, it returns the address of the primary adapter.
        """
        # Optimized version of your 'ipconfig /all | findstr' logic
        cmd = "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object -ExpandProperty MacAddress"
        return self._run_ps(cmd)

    def set_fw_rule(self, ip_address, action="allow"):
        """
        Implements Windows Firewall rules using New-NetFirewallRule.
        """
        direction = "Inbound"
        policy = "Allow" if action == "allow" else "Block"
        
        # Creates a specific rule for the provided IP
        cmd = (
            f"New-NetFirewallRule -DisplayName 'NetSetup_Trust_{ip_address}' "
            f"-Direction {direction} -RemoteAddress {ip_address} "
            f"-Action {policy} -Enabled True"
        )
        return self._run_ps(cmd)