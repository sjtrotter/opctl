import re
import ipaddress


# NOTE: anchor with \A...\Z, NOT ^...$ — in Python `$` also matches just before a
# trailing newline, so `^...$` would accept e.g. "host\n", letting a newline through
# into shell=True command strings (an injection vector).
_HOSTNAME_LABEL = re.compile(r'\A[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\Z')
_MAC_RE = re.compile(r'\A([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}\Z')
_SAFE_IFACE_RE = re.compile(r'\A[a-zA-Z0-9_\-\.\ ]{1,64}\Z')


def validate_hostname(hostname: str) -> str:
    if not isinstance(hostname, str):
        raise ValueError(f"Hostname must be a string: {hostname!r}")
    if not hostname or len(hostname) > 253:
        raise ValueError(f"Invalid hostname (empty or > 253 chars): {hostname!r}")
    labels = hostname.rstrip(".").split(".")
    for label in labels:
        if not _HOSTNAME_LABEL.match(label):
            raise ValueError(f"Invalid hostname label {label!r} in {hostname!r}")
    return hostname


def validate_mac(mac: str) -> str:
    if not isinstance(mac, str) or not _MAC_RE.match(mac):
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return mac


def validate_ip(ip: str) -> str:
    """Accept a bare IP or CIDR like '10.0.0.1/24'."""
    if not isinstance(ip, str):
        raise ValueError(f"IP address must be a string: {ip!r}")
    try:
        if "/" in ip:
            ipaddress.ip_network(ip, strict=False)
        else:
            ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"Invalid IP address or CIDR: {ip!r}")
    return ip


def validate_gateway(gateway: str) -> str:
    """A default gateway is a single next-hop host — a bare IP, never a CIDR."""
    # ipaddress.ip_address() accepts ints (123 -> 0.0.0.123), so guard the type first.
    if not isinstance(gateway, str):
        raise ValueError(f"Gateway must be a string: {gateway!r}")
    if "/" in gateway:
        raise ValueError(f"Gateway must be a bare host, not a CIDR: {gateway!r}")
    try:
        ipaddress.ip_address(gateway)
    except ValueError:
        raise ValueError(f"Invalid gateway address: {gateway!r}")
    return gateway


def validate_dns(dns: str) -> str:
    # ipaddress.ip_address() accepts ints (123 -> 0.0.0.123), so guard the type first.
    if not isinstance(dns, str):
        raise ValueError(f"DNS server must be a string: {dns!r}")
    try:
        ipaddress.ip_address(dns)
    except ValueError:
        raise ValueError(f"Invalid DNS server address: {dns!r}")
    return dns


def validate_interface(name: str) -> str:
    if not isinstance(name, str) or not name or not _SAFE_IFACE_RE.match(name):
        raise ValueError(
            f"Invalid interface name {name!r}: must be 1-64 chars, "
            "alphanumeric, hyphens, underscores, dots, or spaces only"
        )
    return name


def validate_ntp_server(server: str) -> str:
    """An NTP server is a bare IP address or a DNS hostname (not a CIDR)."""
    if not isinstance(server, str) or not server:
        raise ValueError(f"Invalid NTP server: {server!r}")
    try:
        ipaddress.ip_address(server)   # bare IPv4/IPv6, not a network/CIDR
        return server
    except ValueError:
        return validate_hostname(server)


def validate_port(port) -> int:
    try:
        p = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid port: {port!r}")
    if not (1 <= p <= 65535):
        raise ValueError(f"Port out of range (1-65535): {p}")
    return p
