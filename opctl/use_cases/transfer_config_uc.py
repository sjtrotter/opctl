import json
import os
from opctl.domain.models import OpProfile
from opctl.domain.interfaces import IPolicyRepository

class ImportConfigUseCase:
    """Loads a JSON playbook and overwrites the current session state."""
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

        # Inflate via the Domain Model to validate the schema automatically
        profile = OpProfile(imported_data)
        
        # Overwrite the current active session
        self.repo.save_state(profile.to_dict())

class ExportConfigUseCase:
    """Exports the currently staged session state to a shareable JSON playbook."""
    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    def execute(self, file_path: str) -> None:
        staged_dict = self.repo.load_state()
        with open(file_path, 'w') as f:
            json.dump(staged_dict, f, indent=2)