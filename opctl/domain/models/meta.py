from dataclasses import dataclass


@dataclass
class MissionMeta:
    """Optional playbook identity / provenance. Metadata only — never applied to the OS."""
    name: str = ""
    version: int = 1
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "MissionMeta":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", 1),
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version, "description": self.description}
