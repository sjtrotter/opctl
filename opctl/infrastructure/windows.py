import subprocess
import socket
from typing import List
from opctl.domain.interfaces import ISystemAdapter, INetworkAdapter, IFirewallAdapter

class WindowsBackend(ISystemAdapter, INetworkAdapter, IFirewallAdapter):
    """Concrete implementation of all OS interactions using Windows PowerShell."""
    
    def _run_ps(self, cmd: str) -> str:
        """Helper to safely execute PowerShell commands."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"PowerShell Execution Error: {error_msg}\nCommand: {cmd}")

    # --- ISystemAdapter ---
    def set_hostname(self, hostname: str) -> None:
        self._run_ps(f'Rename-Computer -NewName "{hostname}" -Force')

    def get_hostname(self) -> str:
        return socket.gethostname()

    # --- INetworkAdapter ---
    def get_available_interfaces(self) -> List[str]:
        output = self._run_ps('(Get-NetAdapter).Name')
        return [line.strip() for line in output.split('\n') if line.strip()] if output else []

    def set_link_state(self, interface: str, state: str) -> None:
        action = "Enable-NetAdapter" if state.lower() == "up" else "Disable-NetAdapter"
        self._run_ps(f'{action} -Name "{interface}" -Confirm:$false')

    def set_mac_address(self, interface: str, mac: str) -> None:
        clean_mac = mac.replace(":", "").replace("-", "")
        self._run_ps(f'Set-NetAdapter -Name "{interface}" -MacAddress "{clean_mac}" -Confirm:$false')

    def get_mac_address(self, interface: str) -> str:
        mac = self._run_ps(f'(Get-NetAdapter -Name "{interface}").MacAddress')
        return mac.replace("-", ":") if mac else "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        prefix = 24
        if "/" in ip:
            ip, prefix_str = ip.split("/")
            prefix = int(prefix_str)
        self._run_ps(f'Remove-NetIPAddress -InterfaceAlias "{interface}" -Confirm:$false -ErrorAction SilentlyContinue')
        cmd = f'New-NetIPAddress -InterfaceAlias "{interface}" -IPAddress "{ip}" -PrefixLength {prefix}'
        if gateway:
            cmd += f' -DefaultGateway "{gateway}"'
        self._run_ps(cmd)
        if dns_servers:
            dns_str = ",".join([f'"{d}"' for d in dns_servers])
            self._run_ps(f'Set-DnsClientServerAddress -InterfaceAlias "{interface}" -ServerAddresses {dns_str}')

    def configure_dhcp(self, interface: str) -> None:
        self._run_ps(f'Set-NetIPInterface -InterfaceAlias "{interface}" -Dhcp Enabled')
        self._run_ps(f'Set-DnsClientServerAddress -InterfaceAlias "{interface}" -ResetServerAddresses')

    def get_ip_address(self, interface: str) -> str:
        ip = self._run_ps(f'(Get-NetIPAddress -InterfaceAlias "{interface}" -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress')
        return ip.split('\n')[0].strip() if ip else "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        cmd = f'(Get-NetIPInterface -InterfaceAlias "{interface}" -AddressFamily IPv4).Dhcp'
        output = self._run_ps(cmd)
        return output.strip().lower() == "enabled"

    def get_gateway(self, interface: str) -> str:
        cmd = f'(Get-NetRoute -InterfaceAlias "{interface}" -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue).NextHop'
        gw = self._run_ps(cmd)
        return gw if gw else "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        cmd = f'(Get-DnsClientServerAddress -InterfaceAlias "{interface}" -AddressFamily IPv4).ServerAddresses'
        output = self._run_ps(cmd)
        return [line.strip() for line in output.split('\n') if line.strip()] if output else []

    # --- IFirewallAdapter ---
    def flush_managed_rules(self) -> None:
        self._run_ps('Remove-NetFirewallRule -Group "OpCtl" -ErrorAction SilentlyContinue')

    def _apply_port_rules(self, port_overrides: List[str], action: str, display_prefix: str) -> None:
        for rule in port_overrides:
            if ":" not in rule: continue
            ip, port = rule.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["TCP", "UDP"]:
                cmd = (f'New-NetFirewallRule -DisplayName "{display_prefix} {clean_ip}:{port} ({proto})" '
                       f'-Group "OpCtl" -Direction Outbound -Action {action} '
                       f'-RemoteAddress "{clean_ip}" -Protocol {proto} -RemotePort {port}')
                self._run_ps(cmd)

    def _apply_cidr_rules(self, cidrs: List[str], action: str, display_prefix: str) -> None:
        if not cidrs: return
        address_array = ",".join([f'"{cidr}"' for cidr in cidrs])
        cmd = (f'New-NetFirewallRule -DisplayName "{display_prefix} CIDRs" '
               f'-Group "OpCtl" -Direction Outbound -Action {action} -RemoteAddress {address_array}')
        self._run_ps(cmd)

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_port_rules(port_overrides, "Block", "OpCtl v4 Drop")
        self._apply_cidr_rules(cidrs, "Block", "OpCtl v4 Drop")

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_port_rules(port_overrides, "Allow", "OpCtl v4 Allow")
        self._apply_cidr_rules(cidrs, "Allow", "OpCtl v4 Allow")

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_port_rules(port_overrides, "Block", "OpCtl v6 Drop")
        self._apply_cidr_rules(cidrs, "Block", "OpCtl v6 Drop")

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_port_rules(port_overrides, "Allow", "OpCtl v6 Allow")
        self._apply_cidr_rules(cidrs, "Allow", "OpCtl v6 Allow")