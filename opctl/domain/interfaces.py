from abc import ABC, abstractmethod
from typing import List, Optional

class ISystemAdapter(ABC):
    """Controls OS-level identity."""
    @abstractmethod
    def set_hostname(self, hostname: str) -> None: pass
        
    @abstractmethod
    def get_hostname(self) -> str: pass

class INetworkAdapter(ABC):
    """Controls NIC hardware and Layer 3 routing."""
    @abstractmethod
    def get_available_interfaces(self) -> List[str]: pass

    @abstractmethod
    def set_link_state(self, interface: str, state: str) -> None: pass
    
    @abstractmethod
    def set_mac_address(self, interface: str, mac: str) -> None: pass
        
    @abstractmethod
    def get_mac_address(self, interface: str) -> str: pass
    
    @abstractmethod
    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None: pass
    
    @abstractmethod
    def configure_dhcp(self, interface: str) -> None: pass
        
    @abstractmethod
    def get_ip_address(self, interface: str) -> str: pass

    @abstractmethod
    def is_dhcp_enabled(self, interface: str) -> bool: pass

    @abstractmethod
    def get_gateway(self, interface: str) -> str: pass

    @abstractmethod
    def get_dns_servers(self, interface: str) -> List[str]: pass

class IFirewallAdapter(ABC):
    """Controls packet filtering."""
    @abstractmethod
    def flush_managed_rules(self) -> None: pass

    @abstractmethod
    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None: pass

    @abstractmethod
    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str]) -> None: pass

    @abstractmethod
    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None: pass

    @abstractmethod
    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str]) -> None: pass

class IPolicyRepository(ABC):
    """Handles persistence of the Aggregate Root state."""
    @abstractmethod
    def load_state(self) -> Optional[dict]: pass

    @abstractmethod
    def save_state(self, state: dict) -> None: pass