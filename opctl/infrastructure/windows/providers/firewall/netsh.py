import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import WindowsProvider

_PREFIX = "opctl"


class NetshFirewallProvider(WindowsProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "netsh"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("netsh") is not None

    def flush_managed_rules(self) -> None:
        # netsh has no group concept; delete all rules with our name prefix
        try:
            output = self._run_cmd(
                f'netsh advfirewall firewall show rule name=all dir=out verbose'
            )
            for line in output.splitlines():
                if line.startswith("Rule Name:") and _PREFIX in line.lower():
                    name = line.split(":", 1)[1].strip()
                    self._run_cmd(f'netsh advfirewall firewall delete rule name="{name}" dir=out')
        except RuntimeError:
            pass

    def _add_rule(self, name: str, action: str, remote: str,
                  interface: Optional[str] = None,
                  protocol: str = "any", port: Optional[str] = None) -> None:
        cmd = (f'netsh advfirewall firewall add rule name="{name}" '
               f'dir=out action={action} remoteip={remote} protocol={protocol}')
        if port:
            cmd += f" remoteport={port}"
        if interface:
            cmd += f' interfacetype=custom interface="{interface}"'
        self._run_cmd(cmd)

    def _apply(self, cidrs: List[str], ports: List[str], action: str,
               tag: str, interface: Optional[str] = None) -> None:
        for cidr in cidrs:
            self._add_rule(f"{_PREFIX}-{tag}-{cidr}", action, cidr, interface)
        for entry in ports:
            if ":" not in entry:
                continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["tcp", "udp"]:
                self._add_rule(f"{_PREFIX}-{tag}-{clean_ip}:{port}-{proto}",
                               action, clean_ip, interface, proto, port)

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "block", "v4drop", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "allow", "v4allow", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "block", "v6drop", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply(cidrs, port_overrides, "allow", "v6allow", interface)
