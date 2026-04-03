from abc import ABC, abstractmethod
from typing import List, Dict

class ISystemAdapter(ABC):
    """Controls OS-level identity."""
    @abstractmethod
    def set_hostname(self, hostname: str) -> None:
        pass

class INetworkAdapter(ABC):
    """Controls NIC hardware and Layer 3 routing."""
    @abstractmethod
    def set_link_state(self, interface: str, state: str) -> None:
        pass
    
    @abstractmethod
    def set_mac_address(self, interface: str, mac: str) -> None:
        pass
    
    @abstractmethod
    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        pass
    
    @abstractmethod
    def configure_dhcp(self, interface: str) -> None:
        pass

class IFirewallAdapter(ABC):
    """Controls packet filtering. Segregated by protocol for safety and simplicity."""
    @abstractmethod
    def flush_managed_rules(self) -> None:
        pass

    # --- IPv4 Contracts ---
    @abstractmethod
    def apply_ipv4_blocks(self, cidrs: List[str]) -> None:
        pass

    @abstractmethod
    def apply_ipv4_allows(self, cidrs: List[str]) -> None:
        pass

    # --- IPv6 Contracts ---
    @abstractmethod
    def apply_ipv6_blocks(self, cidrs: List[str]) -> None:
        pass

    @abstractmethod
    def apply_ipv6_allows(self, cidrs: List[str]) -> None:
        pass

class IPolicyRepository(ABC):
    """Handles persistence of the Aggregate Root state."""
    @abstractmethod
    def load_state(self) -> dict:
        pass

    @abstractmethod
    def save_state(self, state: dict) -> None:
        pass