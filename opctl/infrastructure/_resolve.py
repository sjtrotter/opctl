from typing import List, Optional, Type
from opctl.domain.interfaces import IProvider


def resolve_provider(preference: str, candidates: List[Type[IProvider]],
                     concern: Optional[str] = None) -> IProvider:
    """Select a provider by name or auto-detect the first available one.

    `concern` (e.g. "firewall") makes the error actionable: it names the missing
    category and the `--<concern>-provider` flag the operator can set.
    """
    if preference != "auto":
        for cls in candidates:
            if cls.provider_name() == preference:
                return cls()
        available = [c.provider_name() for c in candidates]
        label = f"{concern} provider" if concern else "Provider"
        raise ValueError(
            f"{label} '{preference}' not found. Available: {available}"
        )
    for cls in candidates:
        if cls.is_available():
            return cls()
    names = [c.provider_name() for c in candidates]
    kind = concern or "provider"
    raise RuntimeError(
        f"No {kind} backend is available (looked for: {names}). "
        f"Install one of them, or set --{kind}-provider to a tool that is present."
    )
