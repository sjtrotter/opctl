from dataclasses import dataclass

@dataclass
class IdentityProfile:
    """Value Object representing the OS-level identity."""
    hostname: str = ""
    mac_address: str = ""
    randomize_mac: bool = False

    def is_configured(self) -> bool:
        return bool(self.hostname or self.mac_address or self.randomize_mac)