from typing import List, Optional
from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository

class RemoveRuleUseCase:
    """Orchestrates the removal of specific IPs/CIDRs from a policy zone.

    With no interface, the rules are removed from the global policy; with an
    interface, from that interface's local policy (a no-op if it isn't staged).
    """

    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, bucket: str, networks: List[str], interface: Optional[str] = None) -> int:
        """Remove rules from a zone; return how many were actually present and removed."""
        profile = OpProfile.from_dict(self.repo.load_state())

        if interface is not None:
            iface = profile.interfaces.get(interface)
            if iface is None:
                return 0  # nothing staged for that interface; nothing removed
            policy = iface.policy
        else:
            policy = profile.global_policy

        removed = sum(1 for net in networks if policy.remove_rule(bucket, net))
        if removed:
            self.repo.save_state(profile.to_dict())
        return removed