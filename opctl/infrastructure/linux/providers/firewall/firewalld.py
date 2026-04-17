import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import LinuxProvider

_ZONE = "opctl"


class FirewalldProvider(LinuxProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "firewalld"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("firewall-cmd") is not None

    def _cmd(self, *args) -> str:
        return self._run(["firewall-cmd", *args])

    def flush_managed_rules(self) -> None:
        try:
            self._cmd(f"--delete-zone={_ZONE}", "--permanent")
        except RuntimeError:
            pass
        self._cmd(f"--new-zone={_ZONE}", "--permanent")
        self._cmd("--reload")

    def _add_rich_rule(self, family: str, cidr: str, action: str,
                       interface: Optional[str] = None) -> None:
        iface_part = f' source address="{cidr}"'
        rule = f'rule family="{family}"{iface_part} {action}'
        args = [f"--zone={_ZONE}", f"--add-rich-rule={rule}", "--permanent"]
        self._cmd(*args)

    def _add_port_rule(self, family: str, ip: str, port: str, action: str,
                       interface: Optional[str] = None) -> None:
        for proto in ["tcp", "udp"]:
            rule = (f'rule family="{family}" destination address="{ip}" '
                    f'port port="{port}" protocol="{proto}" {action}')
            self._cmd(f"--zone={_ZONE}", f"--add-rich-rule={rule}", "--permanent")

    def _apply(self, cidrs: List[str], ports: List[str], action: str,
               family: str, interface: Optional[str] = None) -> None:
        for cidr in cidrs:
            self._add_rich_rule(family, cidr, action, interface)
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            self._add_port_rule(family, ip.replace("[", "").replace("]", ""), port, action, interface)
        self._cmd("--reload")

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "reject", "ipv4", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "accept", "ipv4", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "reject", "ipv6", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "accept", "ipv6", interface)
