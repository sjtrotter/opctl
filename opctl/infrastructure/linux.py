import subprocess
from typing import List
from opctl.domain.interfaces import ISystemAdapter, INetworkAdapter, IFirewallAdapter

class LinuxBackend(ISystemAdapter, INetworkAdapter, IFirewallAdapter):
    """Concrete implementation of all OS interactions for Linux."""
    
    # --- ISystemAdapter ---
    def set_hostname(self, hostname: str) -> None:
        pass

    def get_hostname(self) -> str:
        return "ghost-01" # Placeholder

    # --- INetworkAdapter ---
    def set_link_state(self, interface: str, state: str) -> None:
        pass

    def set_mac_address(self, interface: str, mac: str) -> None:
        pass

    def get_mac_address(self, interface: str) -> str:
        return "00:11:22:33:44:55" # Placeholder

    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        pass

    def configure_dhcp(self, interface: str) -> None:
        pass

    def get_ip_address(self, interface: str) -> str:
        return "192.168.1.100" # Placeholder

    # --- IFirewallAdapter ---
    def flush_managed_rules(self) -> None:
        pass

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass