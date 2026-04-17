from typing import Dict, Optional
from .backend import BackendConfig
from .system import SystemProfile
from .network import NetworkProfile
from .ntp import NtpProfile
from .interface import InterfaceProfile
from .policy import OpPolicy

class OpProfile:
    """The Aggregate Root containing all modular payloads."""
    
    def __init__(self, system: Optional[SystemProfile] = None,
                 network: Optional[NetworkProfile] = None,
                 ntp: Optional[NtpProfile] = None,
                 interfaces: Optional[Dict[str, InterfaceProfile]] = None,
                 global_policy: Optional[OpPolicy] = None,
                 backend: Optional[BackendConfig] = None):
        self.system = system or SystemProfile()
        self.network = network or NetworkProfile()
        self.ntp = ntp or NtpProfile()
        self.interfaces: Dict[str, InterfaceProfile] = interfaces or {}
        self.global_policy = global_policy or OpPolicy()
        self.backend = backend or BackendConfig()

    @classmethod
    def from_dict(cls, state_dict: Optional[dict]) -> "OpProfile":
        data = state_dict or {}
        
        # 1. Hydrate Global Policy
        global_policy = OpPolicy()
        pol_data = data.get("global_policy", {})
        for zone in ["trusted", "target", "excluded"]:
            for rule in pol_data.get(zone, []):
                global_policy.add_rule(zone, rule)

        # 2. Hydrate Dictionary of Interfaces
        interfaces = {}
        ifaces_data = data.get("interfaces", {})
        for iface_name, iface_dict in ifaces_data.items():
            iface_dict["name"] = iface_name 
            interfaces[iface_name] = InterfaceProfile.from_dict(iface_dict)

        # 3. Hydrate Sub-Profiles safely using dict.get() defaults
        sys_data = data.get("system", {})
        net_data = data.get("network", {})
        ntp_data = data.get("ntp", {})
        be_data = data.get("backend", {})

        return cls(
            system=SystemProfile(
                hostname=sys_data.get("hostname", ""),
                unmanaged_policy=sys_data.get("unmanaged_policy", "ignore")
            ),
            network=NetworkProfile(
                global_dns=net_data.get("global_dns", []),
                default_gateway=net_data.get("default_gateway", ""),
                ipv6_enabled=net_data.get("ipv6_enabled", True),
                ip_forwarding=net_data.get("ip_forwarding", False)
            ),
            ntp=NtpProfile(
                enabled=ntp_data.get("enabled", False),
                servers=ntp_data.get("servers", [])
            ),
            interfaces=interfaces,
            global_policy=global_policy,
            backend=BackendConfig(
                firewall_provider=be_data.get("firewall_provider", "auto"),
                network_provider=be_data.get("network_provider", "auto"),
                system_provider=be_data.get("system_provider", "auto"),
            )
        )

    def to_dict(self) -> dict:
        return {
            "system": self.system.to_dict(),
            "network": self.network.to_dict(),
            "ntp": self.ntp.to_dict(),
            "interfaces": {name: profile.to_dict() for name, profile in self.interfaces.items()},
            "global_policy": {
                "trusted": list(self.global_policy.raw_trusted),
                "target": list(self.global_policy.raw_targets),
                "excluded": list(self.global_policy.raw_excluded)
            },
            "backend": self.backend.to_dict(),
        }