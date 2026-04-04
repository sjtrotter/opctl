from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository

class RemoveRuleUseCase:
    """Orchestrates the removal of specific IPs/CIDRs from a given policy bucket."""
    
    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, bucket: str, networks: list) -> None:
        staged_dict = self.repo.load_state()
        # Use Factory to satisfy strict typing
        profile = OpProfile.from_dict(staged_dict)

        # Remove the targets from the Domain
        for net in networks:
            profile.policy.remove_rule(bucket, net)

        # Save the updated state
        self.repo.save_state(profile.to_dict())