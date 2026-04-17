from dataclasses import dataclass


@dataclass
class BackendConfig:
    """Provider selection for each OS adapter category. 'auto' triggers detection."""
    firewall_provider: str = "auto"
    network_provider: str = "auto"
    system_provider: str = "auto"

    def to_dict(self) -> dict:
        return {
            "firewall_provider": self.firewall_provider,
            "network_provider": self.network_provider,
            "system_provider": self.system_provider,
        }
