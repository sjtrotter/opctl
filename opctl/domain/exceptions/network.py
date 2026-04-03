from .base import OpCtlDomainError

class InvalidNetworkFormatError(OpCtlDomainError):
    """Raised when the operator inputs an unparseable splat, dash, or CIDR."""
    def __init__(self, input_str: str, reason: str):
        self.input_str = input_str
        self.reason = reason
        super().__init__(f"Invalid network format '{input_str}': {reason}")

class ConflictingPolicyError(OpCtlDomainError):
    """Raised if an operator attempts an action that violates defensive safety."""
    def __init__(self, message: str):
        super().__init__(f"Policy Conflict: {message}")