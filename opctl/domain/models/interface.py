from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class InterfaceProfile:
    name: str = ""
    mac_address: str = ""
    randomize_mac: bool = False
    mode: str = "dhcp"
    ip_address: str = ""
    gateway: str = ""
    dns_servers: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "InterfaceProfile":
        if not data: return cls()
        return cls(
            name=data.get("name", ""),
            mac_address=data.get("mac_address", ""),
            randomize_mac=data.get("randomize_mac", False),
            mode=data.get("mode", "dhcp"),
            ip_address=data.get("ip_address", ""),
            gateway=data.get("gateway", ""),
            dns_servers=data.get("dns_servers", [])
        )

    def is_static(self) -> bool:
        return self.mode == "static"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mac_address": self.mac_address,
            "randomize_mac": self.randomize_mac,
            "mode": self.mode,
            "ip_address": self.ip_address,
            "gateway": self.gateway,
            "dns_servers": self.dns_servers
        }