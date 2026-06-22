"""Field-level (semantic) validation of a playbook dict.

Structural validation (blocks are objects, zones are lists) happens earlier in
ImportConfigUseCase; this layer checks the *values* — hostnames, MACs, IPs/CIDRs,
DNS servers, enums (mode, unmanaged policy), provider names, NTP servers, and
firewall rules — and returns every problem found so a bad playbook fails loudly
with a complete, fixable error list.
"""
from typing import List

from opctl.domain.services.validators import (
    validate_hostname, validate_mac, validate_ip, validate_dns, validate_interface,
    validate_ntp_server,
)
from opctl.domain.services.ip_parser import IPParser
from opctl.domain.models.policy import OpPolicy
from opctl.domain.models.backend import BackendConfig
from opctl.domain.exceptions.network import InvalidNetworkFormatError

_MODES = ("dhcp", "static")
_UNMANAGED = ("ignore", "isolate", "disable")
# TypeError is a safety net in case a validator hits a non-string it doesn't guard.
_RULE_ERRORS = (ValueError, TypeError, InvalidNetworkFormatError)


def validate_playbook(data: dict) -> List[str]:
    """Return a list of human-readable field errors (empty list == valid)."""
    errors: List[str] = []

    def check(fn, value, label):
        try:
            fn(value)
        except _RULE_ERRORS as e:
            errors.append(f"{label}: {e}")

    _validate_meta(data.get("meta"), errors)

    system = data.get("system", {})
    if system.get("hostname"):
        check(validate_hostname, system["hostname"], "system.hostname")
    if "unmanaged_policy" in system and system["unmanaged_policy"] not in _UNMANAGED:
        errors.append(f"system.unmanaged_policy must be one of {list(_UNMANAGED)}")

    network = data.get("network", {})
    for dns in network.get("global_dns", []):
        check(validate_dns, dns, "network.global_dns")
    if network.get("default_gateway"):
        check(validate_ip, network["default_gateway"], "network.default_gateway")

    for srv in data.get("ntp", {}).get("servers", []):
        if not _is_host_or_ip(srv):
            errors.append(f"ntp.servers: invalid server {srv!r}")

    backend = data.get("backend", {})
    for field, concern in (("firewall_provider", "firewall"),
                           ("network_provider", "network"),
                           ("system_provider", "system"),
                           ("ntp_provider", "ntp")):
        if field in backend and backend[field] not in BackendConfig.VALID_PROVIDERS[concern]:
            errors.append(
                f"backend.{field} must be one of {list(BackendConfig.VALID_PROVIDERS[concern])}")

    errors.extend(_validate_zones(data.get("global_policy", {}), "global_policy"))

    for name, iface in data.get("interfaces", {}).items():
        check(validate_interface, name, f"interface name {name!r}")
        if iface.get("mac_address"):
            check(validate_mac, iface["mac_address"], f"interface '{name}' mac_address")
        if "mode" in iface and iface["mode"] not in _MODES:
            errors.append(f"interface '{name}' mode must be one of {list(_MODES)}")
        for ip in iface.get("ip_addresses", []):
            check(validate_ip, ip, f"interface '{name}' ip_addresses")
        if iface.get("gateway"):
            check(validate_ip, iface["gateway"], f"interface '{name}' gateway")
        for dns in iface.get("dns_servers", []):
            check(validate_dns, dns, f"interface '{name}' dns_servers")
        errors.extend(_validate_zones(iface.get("policy", {}), f"interface '{name}' policy"))

    return errors


def _validate_meta(meta, errors: List[str]) -> None:
    if not isinstance(meta, dict):
        return
    if "name" in meta and not isinstance(meta["name"], str):
        errors.append("meta.name must be a string")
    if "version" in meta and not isinstance(meta["version"], int):
        errors.append("meta.version must be an integer")
    if "description" in meta and not isinstance(meta["description"], str):
        errors.append("meta.description must be a string")


def _validate_zones(policy: dict, where: str) -> List[str]:
    errs: List[str] = []
    for zone in OpPolicy.ZONES:
        for rule in policy.get(zone, []):
            if not isinstance(rule, str):
                errs.append(f"{where} {zone}: rule must be a string, got {rule!r}")
                continue
            try:
                _validate_rule(rule)
            except _RULE_ERRORS as e:
                errs.append(f"{where} {zone}: invalid rule {rule!r} ({e})")
    return errs


def _validate_rule(rule: str) -> None:
    """Validate a firewall rule: CIDR/splat/dash/IP, optionally `IP:PORT` / `[IPv6]:PORT`."""
    # Mirror OpPolicy._split_ports' port detection.
    if (rule.count(":") == 1 and "." in rule) or "]:" in rule:
        host, _, port = rule.rpartition(":")
        host = host.strip("[]")
        if not (port.isdigit() and 1 <= int(port) <= 65535):
            raise ValueError(f"port out of range: {port!r}")
        IPParser.parse(host)
    else:
        IPParser.parse(rule)


def _is_host_or_ip(value: str) -> bool:
    try:
        validate_ntp_server(value)
        return True
    except ValueError:
        return False
