import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import LinuxProvider

_CHAIN = "OPCTL_OUT"


class IptablesProvider(LinuxProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "iptables"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("iptables") is not None

    def flush_managed_rules(self) -> None:
        try:
            self._run(["iptables", "-F", _CHAIN])
        except RuntimeError:
            self._run(["iptables", "-N", _CHAIN])
            self._run(["iptables", "-I", "OUTPUT", "1", "-j", _CHAIN])

    def _apply_rules(self, cidrs: List[str], ports: List[str], target: str,
                     interface: Optional[str] = None) -> None:
        iface = ["-o", interface] if interface else []
        for cidr in cidrs:
            self._run(["iptables", "-A", _CHAIN, *iface, "-d", cidr, "-j", target])
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["tcp", "udp"]:
                self._run(["iptables", "-A", _CHAIN, *iface,
                           "-p", proto, "-d", clean_ip, "--dport", port, "-j", target])

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_rules(cidrs, port_overrides, "REJECT", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_rules(cidrs, port_overrides, "ACCEPT", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        pass

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        pass
