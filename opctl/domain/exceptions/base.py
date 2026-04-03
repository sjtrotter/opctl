class OpCtlDomainError(Exception):
    """
    Base exception for all opctl domain errors. 
    Allows the CLI to catch any domain-specific error gracefully.
    """
    pass