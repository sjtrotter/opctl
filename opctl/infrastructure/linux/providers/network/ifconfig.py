import os
import re
import shutil
from typing import List
from opctl.domain.interfaces import INetworkAdapter, IProvider
from .._base import LinuxProvider


class IfconfigProvider(LinuxProvider, INetworkAdapter, IProvider):
    """Legacy network provider using net-tools (ifconfig/route)."""

    @classmethod
    def provider_name(cls) -> str:
        return "ifconfig"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ifconfig") is not None

    def get_available_interfaces(self) -> List[str]:
        try:
            return [i for i in os.listdir("/sys/class/net/") if i != "lo"]
        except FileNotFoundError:
            return []

    def set_link_state(self, interface: str, state: str) -> None:
        flag = "up" if state.lower() == "up" else "down"
        self._run(["ifconfig", interface, flag])

    def set_mac_address(self, interface: str, mac: str) -> None:
        self._run(["ifconfig", interface, "hw", "ether", mac])

    def get_mac_address(self, interface: str) -> str:
        try:
            with open(f"/sys/class/net/{interface}/address") as f:
                return f.read().strip().upper()
        except FileNotFoundError:
            return "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        addr, prefix = (ip.split("/") + ["24"])[:2]
        # Convert prefix length to dotted netmask
        bits = int(prefix)
        mask = ".".join(str((0xFFFFFFFF << (32 - bits) >> i) & 0xFF) for i in [24, 16, 8, 0])
        self._run(["ifconfig", interface, addr, "netmask", mask, "up"])
        if gateway:
            try:
                self._run(["route", "del", "default"])
            except RuntimeError:
                pass
            self._run(["route", "add", "default", "gw", gateway])
        if dns_servers:
            with open("/etc/resolv.conf", "w") as f:
                for dns in dns_servers:
                    f.write(f"nameserver {dns}\n")

    def configure_dhcp(self, interface: str) -> None:
        self._run(["ifconfig", interface, "0.0.0.0"])
        self._run(["dhclient", interface])

    def get_ip_address(self, interface: str) -> str:
        try:
            output = self._run(["ifconfig", interface])
            match = re.search(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", output)
            return match.group(1) if match else "Unassigned"
        except RuntimeError:
            return "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        if os.path.exists(f"/var/lib/dhcp/dhclient.{interface}.leases"):
            return True
        try:
            return f"dhclient {interface}" in self._run(["ps", "ax"])
        except Exception:
            return False

    def get_gateway(self, interface: str) -> str:
        try:
            output = self._run(["route", "-n"])
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 8 and parts[0] == "0.0.0.0" and parts[7] == interface:
                    return parts[1]
            return "None"
        except RuntimeError:
            return "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        try:
            with open("/etc/resolv.conf") as f:
                return [line.split()[1] for line in f if line.startswith("nameserver")]
        except FileNotFoundError:
            return []
