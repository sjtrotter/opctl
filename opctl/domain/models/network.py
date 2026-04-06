from dataclasses import dataclass, field
from typing import List

@dataclass
class NetworkProfile:
    """Global L3/L4 Network Stack toggles."""
    global_dns: List[str] = field(default_factory=list)
    default_gateway: str = ""
    ipv6_enabled: bool = True
    ip_forwarding: bool = False

    def to_dict(self) -> dict:
        return {
            "global_dns": self.global_dns, 
            "default_gateway": self.default_gateway,
            "ipv6_enabled": self.ipv6_enabled, 
            "ip_forwarding": self.ip_forwarding
        }