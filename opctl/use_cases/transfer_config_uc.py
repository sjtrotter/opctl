import json
import os
from opctl.domain.models import OpProfile
from opctl.domain.models.policy import OpPolicy
from opctl.domain.services.playbook_validator import validate_playbook
from opctl.domain.interfaces import IPolicyRepository

class ImportConfigUseCase:
    """Loads a JSON playbook and replaces the current session state."""

    # Top-level blocks that must be JSON objects when present.
    _OBJECT_BLOCKS = ("system", "network", "ntp", "backend", "global_policy", "interfaces")
    # (block, field) pairs that must be JSON lists when present.
    _LIST_FIELDS = (("network", "global_dns"), ("ntp", "servers"))
    _IFACE_LIST_FIELDS = ("ip_addresses", "dns_servers")

    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Playbook file not found: {file_path}")

        with open(file_path, 'r') as f:
            try:
                imported_data = json.load(f)
            except json.JSONDecodeError:
                raise ValueError("Playbook must be a valid JSON file.")

        self._validate_structure(imported_data)

        # Field-level / semantic validation — collect ALL problems and fail loudly.
        errors = validate_playbook(imported_data)
        if errors:
            raise ValueError("invalid playbook:\n  - " + "\n  - ".join(errors))

        # from_dict normalizes the (now validated) OpProfile shape and drops unknown keys.
        profile = OpProfile.from_dict(imported_data)

        # Replace the current active session
        self.repo.save_state(profile.to_dict())

    @classmethod
    def _validate_structure(cls, data) -> None:
        """Verify the playbook is shaped like an OpProfile (raises ValueError)."""
        if not isinstance(data, dict):
            raise ValueError("Playbook must be a JSON object.")

        for block in cls._OBJECT_BLOCKS:
            if block in data and not isinstance(data[block], dict):
                raise ValueError(f"Playbook '{block}' must be an object.")

        # List-typed fields must be lists, else the field validator iterates a
        # scalar and raises an uncaught TypeError (or shreds a string char-by-char).
        for block, field in cls._LIST_FIELDS:
            value = data.get(block, {}).get(field)
            if value is not None and not isinstance(value, list):
                raise ValueError(f"Playbook '{block}.{field}' must be a list.")

        cls._validate_zones(data.get("global_policy", {}), "global_policy")

        for name, iface in data.get("interfaces", {}).items():
            if not isinstance(iface, dict):
                raise ValueError(f"Playbook interface '{name}' must be an object.")
            for field in cls._IFACE_LIST_FIELDS:
                if field in iface and not isinstance(iface[field], list):
                    raise ValueError(f"Playbook interface '{name}' {field} must be a list.")
            policy = iface.get("policy", {})
            if not isinstance(policy, dict):
                raise ValueError(f"Playbook interface '{name}' policy must be an object.")
            cls._validate_zones(policy, f"interface '{name}' policy")

    @staticmethod
    def _validate_zones(policy: dict, where: str) -> None:
        for zone in OpPolicy.ZONES:
            if zone in policy and not isinstance(policy[zone], list):
                raise ValueError(f"{where} zone '{zone}' must be a list of rules.")

class ExportConfigUseCase:
    """Exports the currently staged session state to a shareable JSON playbook."""
    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, file_path: str) -> None:
        staged_dict = self.repo.load_state()
        with open(file_path, 'w') as f:
            json.dump(staged_dict, f, indent=2)