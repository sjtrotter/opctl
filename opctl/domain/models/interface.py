from dataclasses import dataclass, field
from typing import List

@dataclass
class InterfaceProfile:
    """Value Object representing Layer 3 connectivity."""
    name: str = ""
    mode: str = "dhcp"
    ip_address: str = ""
    gateway: str = ""
    dns_servers: List[str] = field(default_factory=list)

    def is_static(self) -> bool:
        return self.mode == "static"