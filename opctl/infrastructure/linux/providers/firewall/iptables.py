import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import LinuxProvider

_CHAIN = "OPCTL_OUT"
_IP6TABLES = "ip6tables"


class IptablesProvider(LinuxProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "iptables"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("iptables") is not None

    def _flush_chain(self, cmd: str) -> None:
        try:
            self._run([cmd, "-F", _CHAIN])
        except RuntimeError:
            self._run([cmd, "-N", _CHAIN])
            self._run([cmd, "-I", "OUTPUT", "1", "-j", _CHAIN])

    def flush_managed_rules(self) -> None:
        self._flush_chain("iptables")
        # ip6tables ships with iptables on most hosts but isn't guaranteed; skip
        # IPv6 gracefully when it's absent rather than erroring the commit.
        if shutil.which(_IP6TABLES):
            self._flush_chain(_IP6TABLES)

    def _apply_rules(self, cmd: str, cidrs: List[str], ports: List[str], target: str,
                     interface: Optional[str] = None) -> None:
        iface = ["-o", interface] if interface else []
        for cidr in cidrs:
            self._run([cmd, "-A", _CHAIN, *iface, "-d", cidr, "-j", target])
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ("tcp", "udp"):
                self._run([cmd, "-A", _CHAIN, *iface,
                           "-p", proto, "-d", clean_ip, "--dport", port, "-j", target])

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_rules("iptables", cidrs, port_overrides, "REJECT", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_rules("iptables", cidrs, port_overrides, "ACCEPT", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        if shutil.which(_IP6TABLES):
            self._apply_rules(_IP6TABLES, cidrs, port_overrides, "REJECT", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        if shutil.which(_IP6TABLES):
            self._apply_rules(_IP6TABLES, cidrs, port_overrides, "ACCEPT", interface)
