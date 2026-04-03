from .identity import IdentityProfile
from .interface import InterfaceProfile
from .policy import OpPolicy

class OpProfile:
    """
    THE AGGREGATE ROOT. 
    Represents the complete, declarative state of the cyber operations workstation.
    """
    def __init__(self, state_dict: dict = None):
        if state_dict is None:
            state_dict = {}

        self.identity = IdentityProfile(**state_dict.get("identity", {}))
        self.interface = InterfaceProfile(**state_dict.get("interface", {}))
        
        self.policy = OpPolicy()
        policy_data = state_dict.get("policy", {})
        
        for rule in policy_data.get("trusted", []):
            self.policy.add_rule("trusted", rule)
        for rule in policy_data.get("targets", []):
            self.policy.add_rule("target", rule)
        for rule in policy_data.get("excluded", []):
            self.policy.add_rule("excluded", rule)

    def to_dict(self) -> dict:
        """Serializes the aggregate back to a raw dictionary for repository persistence."""
        return {
            "identity": self.identity.__dict__,
            "interface": self.interface.__dict__,
            "policy": {
                "trusted": list(self.policy.raw_trusted),
                "targets": list(self.policy.raw_targets),
                "excluded": list(self.policy.raw_excluded)
            }
        }