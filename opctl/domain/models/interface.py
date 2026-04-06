from dataclasses import dataclass, field
from typing import List
from .policy import OpPolicy

@dataclass
class InterfaceProfile:
    """Per-NIC hardware and addressing."""
    name: str = ""
    enabled: bool = True
    mac_address: str = ""
    randomize_mac: bool = False
    mode: str = "dhcp"
    ip_addresses: List[str] = field(default_factory=list)
    gateway: str = "" 
    
    # --- NEW: DNS and DHCP Overrides ---
    dns_servers: List[str] = field(default_factory=list)
    dhcp_ignore_dns: bool = False
    dhcp_ignore_gw: bool = False
    
    policy: OpPolicy = field(default_factory=OpPolicy)

    @classmethod
    def from_dict(cls, data: dict) -> "InterfaceProfile":
        local_policy = OpPolicy()
        pol_data = data.get("policy", {})
        for zone in ["trusted", "target", "excluded"]:
            for rule in pol_data.get(zone, []):
                local_policy.add_rule(zone, rule)

        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            mac_address=data.get("mac_address", ""),
            randomize_mac=data.get("randomize_mac", False),
            mode=data.get("mode", "dhcp"),
            ip_addresses=data.get("ip_addresses", []),
            gateway=data.get("gateway", ""),
            dns_servers=data.get("dns_servers", []),
            dhcp_ignore_dns=data.get("dhcp_ignore_dns", False),
            dhcp_ignore_gw=data.get("dhcp_ignore_gw", False),
            policy=local_policy
        )

    def is_static(self) -> bool:
        return self.mode == "static"

    def to_dict(self) -> dict:
        return {
            "name": self.name, 
            "enabled": self.enabled, 
            "mac_address": self.mac_address,
            "randomize_mac": self.randomize_mac, 
            "mode": self.mode,
            "ip_addresses": self.ip_addresses, 
            "gateway": self.gateway,
            "dns_servers": self.dns_servers,
            "dhcp_ignore_dns": self.dhcp_ignore_dns,
            "dhcp_ignore_gw": self.dhcp_ignore_gw,
            "policy": {
                "trusted": list(self.policy.raw_trusted),
                "target": list(self.policy.raw_targets),
                "excluded": list(self.policy.raw_excluded)
            }
        }