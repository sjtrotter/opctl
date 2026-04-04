from typing import Optional
from .identity import IdentityProfile
from .interface import InterfaceProfile
from .policy import OpPolicy

class OpProfile:
    def __init__(self, identity: Optional[IdentityProfile] = None, 
                 interface: Optional[InterfaceProfile] = None, 
                 policy: Optional[OpPolicy] = None):
        self.identity = identity or IdentityProfile()
        self.interface = interface or InterfaceProfile()
        self.policy = policy or OpPolicy()

    @classmethod
    def from_dict(cls, state_dict: Optional[dict]) -> "OpProfile":
        data = state_dict or {}
        policy = OpPolicy()
        
        pol_data = data.get("policy", {})
        for zone in ["trusted", "target", "excluded"]:
            for rule in pol_data.get(zone, []):
                policy.add_rule(zone, rule)

        return cls(
            identity=IdentityProfile.from_dict(data.get("identity")),
            interface=InterfaceProfile.from_dict(data.get("interface")),
            policy=policy
        )

    def to_dict(self) -> dict:
        return {
            "identity": self.identity.to_dict(),
            "interface": self.interface.to_dict(),
            "policy": {
                "trusted": list(self.policy.raw_trusted),
                "target": list(self.policy.raw_targets),
                "excluded": list(self.policy.raw_excluded)
            }
        }