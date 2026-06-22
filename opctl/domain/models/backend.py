from dataclasses import dataclass


@dataclass
class BackendConfig:
    """Provider selection for each OS adapter category. 'auto' triggers detection."""

    # Valid provider identifiers per concern (the union across OSes); 'auto' detects.
    # Single source of truth for both the `backend` command's choices and playbook
    # validation. (No type annotation -> a class constant, not a dataclass field.)
    VALID_PROVIDERS = {
        "firewall": ("auto", "iptables", "firewalld", "ufw", "powershell", "netsh"),
        "network": ("auto", "iproute2", "nmcli", "ifconfig", "powershell", "netsh"),
        "system": ("auto", "hostnamectl", "hostname", "powershell", "wmic"),
    }

    firewall_provider: str = "auto"
    network_provider: str = "auto"
    system_provider: str = "auto"

    def to_dict(self) -> dict:
        return {
            "firewall_provider": self.firewall_provider,
            "network_provider": self.network_provider,
            "system_provider": self.system_provider,
        }
