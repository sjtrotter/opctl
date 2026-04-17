from typing import List, Type
from opctl.domain.interfaces import IProvider


def resolve_provider(preference: str, candidates: List[Type[IProvider]]) -> IProvider:
    """Select a provider by name or auto-detect the first available one."""
    if preference != "auto":
        for cls in candidates:
            if cls.provider_name() == preference:
                return cls()
        available = [c.provider_name() for c in candidates]
        raise ValueError(f"Provider '{preference}' not found. Available: {available}")
    for cls in candidates:
        if cls.is_available():
            return cls()
    raise RuntimeError(
        f"No available provider found among: {[c.provider_name() for c in candidates]}"
    )
