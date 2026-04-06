from dataclasses import dataclass

@dataclass
class SystemProfile:
    """Core OS identity and behavior."""
    hostname: str = ""
    unmanaged_policy: str = "ignore" # ignore, isolate, disable

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname, 
            "unmanaged_policy": self.unmanaged_policy
        }