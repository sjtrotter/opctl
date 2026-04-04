from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository

class BulkConfigureUseCase:
    """Handles applying multiple configuration parameters at once from CLI flags."""
    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, config_args: dict) -> None:
        staged_dict = self.repo.load_state()
        # Use the factory method to satisfy strict type checking
        profile = OpProfile.from_dict(staged_dict)

        if config_args.get("hostname"):
            profile.identity.hostname = config_args["hostname"]

        if config_args.get("interface"):
            profile.interface.name = config_args["interface"]
            
        if config_args.get("mac"):
            if config_args["mac"].lower() == "random":
                profile.interface.randomize_mac = True
                profile.interface.mac_address = ""
            else:
                profile.interface.mac_address = config_args["mac"]
                profile.interface.randomize_mac = False
                
        if config_args.get("mode"):
            profile.interface.mode = config_args["mode"]

        for t in config_args.get("targets") or []:
            profile.policy.add_rule("target", t)
        for t in config_args.get("trusted") or []:
            profile.policy.add_rule("trusted", t)
        for e in config_args.get("excludes") or []:
            profile.policy.add_rule("excluded", e)

        self.repo.save_state(profile.to_dict())