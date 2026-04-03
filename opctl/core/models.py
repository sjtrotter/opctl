import ipaddress
from .parsers import IPParser

class OpPolicy:
    """
    The declarative domain model for the workstation's network policy.
    Maintains the raw rules and compiles the final actionable CIDR blocks.
    """
    def __init__(self, state_dict):
        # Raw string inputs from the operator (loaded from JSON)
        self.raw_trusted = set(state_dict.get("trusted", []))
        self.raw_targets = set(state_dict.get("targets", []))
        self.raw_excluded = set(state_dict.get("excluded", []))

    def add_rule(self, zone, input_str):
        """Stages a new rule string into the correct zone."""
        if zone == "trusted":
            self.raw_trusted.add(input_str)
        elif zone == "target":
            self.raw_targets.add(input_str)
        elif zone == "excluded":
            self.raw_excluded.add(input_str)

    def compile(self):
        """
        The compiler. Translates raw strings, applies the safety valve 
        (subtraction), and returns the minimized CIDR blocks for the OS.
        """
        # 1. Parse all strings into pure IP object sets
        trusted_ips = self._parse_set(self.raw_trusted)
        target_ips = self._parse_set(self.raw_targets)
        excluded_ips = self._parse_set(self.raw_excluded)

        # 2. Set Subtraction (The Safety Valve)
        clean_trusted = trusted_ips - excluded_ips
        clean_targets = target_ips - excluded_ips

        # 3. Collapse to minimal CIDRs
        return {
            "trusted_cidrs": [str(net) for net in ipaddress.collapse_addresses(clean_trusted)],
            "target_cidrs": [str(net) for net in ipaddress.collapse_addresses(clean_targets)],
            "blocked_cidrs": [str(net) for net in ipaddress.collapse_addresses(excluded_ips)]
        }

    def _parse_set(self, raw_set):
        """Helper to pass raw strings through the IPParser."""
        ip_set = set()
        for raw_str in raw_set:
            ip_set.update(IPParser.expand(raw_str))
        return ip_set