import re
import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import LinuxProvider

_COMMENT = "opctl"


class UfwProvider(LinuxProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "ufw"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ufw") is not None

    def flush_managed_rules(self) -> None:
        try:
            # Delete all rules carrying the opctl comment
            output = self._run(["ufw", "status", "numbered"])
            # Collect rule numbers in reverse order to avoid index shifting on delete
            numbers = []
            for line in output.splitlines():
                if _COMMENT in line:
                    m = re.match(r"\[\s*(\d+)\]", line)
                    if m:
                        numbers.append(int(m.group(1)))
            for n in sorted(numbers, reverse=True):
                self._run(["ufw", "--force", "delete", str(n)])
        except RuntimeError:
            pass

    def _apply(self, cidrs: List[str], ports: List[str], action: str,
               interface: Optional[str] = None) -> None:
        iface = ["out", "on", interface] if interface else ["out"]
        for cidr in cidrs:
            self._run(["ufw", action, *iface, "to", cidr,
                       "comment", _COMMENT])
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["tcp", "udp"]:
                self._run(["ufw", action, *iface, "to", clean_ip,
                           "port", port, "proto", proto, "comment", _COMMENT])

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "deny", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "allow", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "deny", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "allow", interface)
