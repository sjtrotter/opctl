from dataclasses import dataclass, field
from typing import List

@dataclass
class NtpProfile:
    """Time synchronization settings."""
    enabled: bool = False
    servers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled, 
            "servers": self.servers
        }