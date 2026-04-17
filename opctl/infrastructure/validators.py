import re
import ipaddress


_HOSTNAME_LABEL = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$')
_MAC_RE = re.compile(r'^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$')
_SAFE_IFACE_RE = re.compile(r'^[a-zA-Z0-9_\-\.\ ]{1,64}$')


def validate_hostname(hostname: str) -> str:
    if not hostname or len(hostname) > 253:
        raise ValueError(f"Invalid hostname (empty or > 253 chars): {hostname!r}")
    labels = hostname.rstrip(".").split(".")
    for label in labels:
        if not _HOSTNAME_LABEL.match(label):
            raise ValueError(f"Invalid hostname label {label!r} in {hostname!r}")
    return hostname


def validate_mac(mac: str) -> str:
    if not _MAC_RE.match(mac):
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return mac


def validate_ip(ip: str) -> str:
    """Accept a bare IP or CIDR like '10.0.0.1/24'."""
    try:
        if "/" in ip:
            ipaddress.ip_network(ip, strict=False)
        else:
            ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"Invalid IP address or CIDR: {ip!r}")
    return ip


def validate_dns(dns: str) -> str:
    try:
        ipaddress.ip_address(dns)
    except ValueError:
        raise ValueError(f"Invalid DNS server address: {dns!r}")
    return dns


def validate_interface(name: str) -> str:
    if not name or not _SAFE_IFACE_RE.match(name):
        raise ValueError(
            f"Invalid interface name {name!r}: must be 1-64 chars, "
            "alphanumeric, hyphens, underscores, dots, or spaces only"
        )
    return name


def validate_port(port) -> int:
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid port: {port!r}")
    if not (1 <= p <= 65535):
        raise ValueError(f"Port out of range (1-65535): {p}")
    return p
