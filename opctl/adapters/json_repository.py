import json
import os
from opctl.domain.interfaces import IPolicyRepository

class JsonPolicyRepository(IPolicyRepository):
    """Concrete implementation of the repository using a local JSON file."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_state(self) -> dict:
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {} # Return clean state if file is corrupted
        return {}

    def save_state(self, state: dict) -> None:
        with open(self.file_path, 'w') as f:
            json.dump(state, f, indent=2)