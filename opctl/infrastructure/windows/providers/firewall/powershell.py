import shutil
from typing import List, Optional
from opctl.domain.interfaces import IFirewallAdapter, IProvider
from .._base import WindowsProvider

_GROUP = "OpCtl"


class PowerShellFirewallProvider(WindowsProvider, IFirewallAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "powershell"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("powershell") is not None

    def flush_managed_rules(self) -> None:
        self._run_ps(f'Remove-NetFirewallRule -Group "{_GROUP}" -ErrorAction SilentlyContinue')

    def _apply_port_rules(self, ports: List[str], action: str, prefix: str,
                          interface: Optional[str] = None) -> None:
        iface = f' -InterfaceAlias "{interface}"' if interface else ""
        for rule in ports:
            if ":" not in rule:
                continue
            ip, port = rule.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["TCP", "UDP"]:
                self._run_ps(
                    f'New-NetFirewallRule -DisplayName "{prefix} {clean_ip}:{port} ({proto})" '
                    f'-Group "{_GROUP}" -Direction Outbound -Action {action} '
                    f'-RemoteAddress "{clean_ip}" -Protocol {proto} -RemotePort {port}{iface}'
                )

    def _apply_cidr_rules(self, cidrs: List[str], action: str, prefix: str,
                          interface: Optional[str] = None) -> None:
        if not cidrs:
            return
        addr_array = ",".join(f'"{c}"' for c in cidrs)
        iface = f' -InterfaceAlias "{interface}"' if interface else ""
        self._run_ps(
            f'New-NetFirewallRule -DisplayName "{prefix} CIDRs" '
            f'-Group "{_GROUP}" -Direction Outbound -Action {action} '
            f'-RemoteAddress {addr_array}{iface}'
        )

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_port_rules(port_overrides, "Block", "OpCtl v4 Drop", interface)
        self._apply_cidr_rules(cidrs, "Block", "OpCtl v4 Drop", interface)

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_port_rules(port_overrides, "Allow", "OpCtl v4 Allow", interface)
        self._apply_cidr_rules(cidrs, "Allow", "OpCtl v4 Allow", interface)

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_port_rules(port_overrides, "Block", "OpCtl v6 Drop", interface)
        self._apply_cidr_rules(cidrs, "Block", "OpCtl v6 Drop", interface)

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str],
                          interface: Optional[str] = None) -> None:
        self._apply_port_rules(port_overrides, "Allow", "OpCtl v6 Allow", interface)
        self._apply_cidr_rules(cidrs, "Allow", "OpCtl v6 Allow", interface)
