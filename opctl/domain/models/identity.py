from dataclasses import dataclass
from typing import Optional

@dataclass
class IdentityProfile:
    hostname: str = ""

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "IdentityProfile":
        if not data: return cls()
        return cls(hostname=data.get("hostname", ""))

    def to_dict(self) -> dict:
        return {"hostname": self.hostname}