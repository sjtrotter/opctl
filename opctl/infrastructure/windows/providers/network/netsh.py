import re
import shutil
from typing import List
from opctl.domain.interfaces import INetworkAdapter, IProvider
from .._base import WindowsProvider


class NetshNetworkProvider(WindowsProvider, INetworkAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "netsh"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("netsh") is not None

    def get_available_interfaces(self) -> List[str]:
        output = self._run_cmd("netsh interface show interface")
        interfaces = []
        for line in output.splitlines()[3:]:
            parts = line.split()
            if len(parts) >= 4:
                interfaces.append(" ".join(parts[3:]))
        return interfaces

    def set_link_state(self, interface: str, state: str) -> None:
        self.validate_interface(interface)
        action = "enable" if state.lower() == "up" else "disable"
        self._run_cmd(f'netsh interface set interface "{interface}" admin={action}')

    def set_mac_address(self, interface: str, mac: str) -> None:
        # netsh does not support MAC spoofing; requires registry edit
        raise NotImplementedError(
            "MAC address changes via netsh are not supported. Use PowerShell provider."
        )

    def get_mac_address(self, interface: str) -> str:
        self.validate_interface(interface)
        output = self._run_cmd(f'getmac /fo csv /nh /v')
        for line in output.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            # CSV columns: Connection Name, Network Adapter, Physical Address, Transport Name
            if len(parts) >= 3 and parts[0].lower() == interface.lower():
                return parts[2].replace("-", ":")
        return "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str,
                         dns_servers: List[str]) -> None:
        self.validate_interface(interface)
        self.validate_ip(ip)
        if gateway:
            self.validate_ip(gateway)
        for dns in dns_servers:
            self.validate_dns(dns)
        addr, prefix = (ip.split("/") + ["24"])[:2]
        bits = int(prefix)
        mask = ".".join(str((0xFFFFFFFF << (32 - bits) >> i) & 0xFF) for i in [24, 16, 8, 0])
        cmd = (f'netsh interface ip set address name="{interface}" '
               f'static {addr} {mask}')
        if gateway:
            cmd += f" {gateway}"
        self._run_cmd(cmd)
        for i, dns in enumerate(dns_servers):
            src = "primary" if i == 0 else "add"
            self._run_cmd(f'netsh interface ip {src} dns name="{interface}" {dns}')

    def configure_dhcp(self, interface: str) -> None:
        self.validate_interface(interface)
        self._run_cmd(f'netsh interface ip set address name="{interface}" dhcp')
        self._run_cmd(f'netsh interface ip set dns name="{interface}" dhcp')

    def get_ip_address(self, interface: str) -> str:
        try:
            output = self._run_cmd(f'netsh interface ip show address "{interface}"')
            for line in output.splitlines():
                if "IP Address" in line:
                    return line.split(":")[-1].strip()
            return "Unassigned"
        except RuntimeError:
            return "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        try:
            output = self._run_cmd(f'netsh interface ip show address "{interface}"')
            return "DHCP" in output
        except RuntimeError:
            return False

    def get_gateway(self, interface: str) -> str:
        try:
            output = self._run_cmd(f'netsh interface ip show address "{interface}"')
            for line in output.splitlines():
                if "Default Gateway" in line:
                    gw = line.split(":")[-1].strip()
                    return gw if gw else "None"
            return "None"
        except RuntimeError:
            return "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        try:
            output = self._run_cmd(f'netsh interface ip show dns "{interface}"')
            servers = []
            for line in output.splitlines():
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    servers.append(m.group(1))
            return servers
        except RuntimeError:
            return []
