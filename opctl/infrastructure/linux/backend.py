from typing import List, Optional

from opctl.domain.interfaces import ISystemAdapter, INetworkAdapter, IFirewallAdapter
from opctl.domain.models.backend import BackendConfig
from opctl.infrastructure._resolve import resolve_provider

from .providers.system.hostnamectl import HostnamectlProvider
from .providers.system.hostname import HostnameProvider
from .providers.network.iproute2 import Iproute2Provider
from .providers.network.nmcli import NmcliProvider
from .providers.network.ifconfig import IfconfigProvider
from .providers.firewall.firewalld import FirewalldProvider
from .providers.firewall.ufw import UfwProvider
from .providers.firewall.iptables import IptablesProvider

_SYSTEM_PROVIDERS = [HostnamectlProvider, HostnameProvider]
_NETWORK_PROVIDERS = [NmcliProvider, Iproute2Provider, IfconfigProvider]
_FIREWALL_PROVIDERS = [FirewalldProvider, UfwProvider, IptablesProvider]


class LinuxBackend(ISystemAdapter, INetworkAdapter, IFirewallAdapter):

    def __init__(self, config: Optional[BackendConfig] = None):
        cfg = config or BackendConfig()
        self._system: ISystemAdapter = resolve_provider(cfg.system_provider, _SYSTEM_PROVIDERS)
        self._network: INetworkAdapter = resolve_provider(cfg.network_provider, _NETWORK_PROVIDERS)
        self._firewall: IFirewallAdapter = resolve_provider(cfg.firewall_provider, _FIREWALL_PROVIDERS)

    # --- ISystemAdapter ---
    def set_hostname(self, hostname: str) -> None:
        self._system.set_hostname(hostname)

    def get_hostname(self) -> str:
        return self._system.get_hostname()

    # --- INetworkAdapter ---
    def get_available_interfaces(self) -> List[str]:
        return self._network.get_available_interfaces()

    def set_link_state(self, interface: str, state: str) -> None:
        self._network.set_link_state(interface, state)

    def set_mac_address(self, interface: str, mac: str) -> None:
        self._network.set_mac_address(interface, mac)

    def get_mac_address(self, interface: str) -> str:
        return self._network.get_mac_address(interface)

    def configure_static(self, interface: str, ip: str, gateway: str,
                         dns_servers: List[str]) -> None:
        self._network.configure_static(interface, ip, gateway, dns_servers)

    def configure_dhcp(self, interface: str) -> None:
        self._network.configure_dhcp(interface)

    def get_ip_address(self, interface: str) -> str:
        return self._network.get_ip_address(interface)

    def is_dhcp_enabled(self, interface: str) -> bool:
        return self._network.is_dhcp_enabled(interface)

    def get_gateway(self, interface: str) -> str:
        return self._network.get_gateway(interface)

    def get_dns_servers(self, interface: str) -> List[str]:
        return self._network.get_dns_servers(interface)

    # --- IFirewallAdapter ---
    def flush_managed_rules(self) -> None:
        self._firewall.flush_managed_rules()

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._firewall.apply_ipv4_blocks(cidrs, port_overrides, interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._firewall.apply_ipv4_allows(cidrs, port_overrides, interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._firewall.apply_ipv6_blocks(cidrs, port_overrides, interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._firewall.apply_ipv6_allows(cidrs, port_overrides, interface)
