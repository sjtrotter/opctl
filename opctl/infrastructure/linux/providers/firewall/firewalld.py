import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import LinuxProvider

# A managed direct chain in the OUTPUT path, mirroring the iptables provider.
# firewalld's zone/rich-rule model can't express per-NIC egress in a single shared
# zone, so we drive netfilter directly via `firewall-cmd --direct`, which supports
# both IPv4 and IPv6 and the standard `-o <iface> -d <cidr>` egress match.
_TABLE = "filter"
_CHAIN = "OPCTL_OUT"


class FirewalldProvider(LinuxProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "firewalld"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("firewall-cmd") is not None

    def _direct(self, *args) -> str:
        # Runtime direct rules: applied immediately, like the iptables provider
        # (non-persistent — re-applied on each `execute`).
        return self._run(["firewall-cmd", "--direct", *args])

    def _has_chain(self, family: str) -> bool:
        try:
            self._direct("--query-chain", family, _TABLE, _CHAIN)
            return True
        except RuntimeError:
            return False

    def flush_managed_rules(self) -> None:
        self._priority = 0  # reset the per-commit insertion counter (see _next_priority)
        for family in ("ipv4", "ipv6"):
            if self._has_chain(family):
                self._direct("--remove-rules", family, _TABLE, _CHAIN)
            else:
                self._direct("--add-chain", family, _TABLE, _CHAIN)
                self._direct("--add-rule", family, _TABLE, "OUTPUT", "0", "-j", _CHAIN)

    def _next_priority(self) -> str:
        # firewalld direct rules with EQUAL priority have undefined order. To mirror
        # iptables `-A` insertion order (so REJECT rules stay above later ACCEPTs and
        # specific port rules above broad allows), give each rule a monotonically
        # increasing priority = its insertion index within the commit.
        prio = getattr(self, "_priority", 0)
        self._priority = prio + 1
        return str(prio)

    def _apply(self, cidrs: List[str], ports: List[str], target: str,
               family: str, interface: Optional[str] = None) -> None:
        iface = ["-o", interface] if interface else []
        for cidr in cidrs:
            self._direct("--add-rule", family, _TABLE, _CHAIN, self._next_priority(),
                         *iface, "-d", cidr, "-j", target)
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ("tcp", "udp"):
                self._direct("--add-rule", family, _TABLE, _CHAIN, self._next_priority(),
                             *iface, "-p", proto, "-d", clean_ip, "--dport", port, "-j", target)

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "REJECT", "ipv4", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "ACCEPT", "ipv4", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "REJECT", "ipv6", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "ACCEPT", "ipv6", interface)
