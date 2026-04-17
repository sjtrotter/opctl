import os
import shutil
from typing import List
from opctl.domain.interfaces import INetworkAdapter, IProvider
from .._base import LinuxProvider


class Iproute2Provider(LinuxProvider, INetworkAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "iproute2"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ip") is not None

    def get_available_interfaces(self) -> List[str]:
        try:
            return [i for i in os.listdir("/sys/class/net/") if i != "lo"]
        except FileNotFoundError:
            return []

    def set_link_state(self, interface: str, state: str) -> None:
        self._run(["ip", "link", "set", interface, state.lower()])

    def set_mac_address(self, interface: str, mac: str) -> None:
        self._run(["ip", "link", "set", interface, "address", mac])

    def get_mac_address(self, interface: str) -> str:
        try:
            with open(f"/sys/class/net/{interface}/address") as f:
                return f.read().strip().upper()
        except FileNotFoundError:
            return "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        self._run(["ip", "addr", "flush", "dev", interface])
        self._run(["ip", "addr", "add", ip, "dev", interface])
        if gateway:
            self._run(["ip", "route", "add", "default", "via", gateway, "dev", interface])
        if dns_servers:
            with open("/etc/resolv.conf", "w") as f:
                for dns in dns_servers:
                    f.write(f"nameserver {dns}\n")

    def configure_dhcp(self, interface: str) -> None:
        self._run(["ip", "addr", "flush", "dev", interface])
        self._run(["dhclient", interface])

    def get_ip_address(self, interface: str) -> str:
        try:
            output = self._run(["ip", "-4", "-o", "addr", "show", interface])
            return output.split()[3].split("/")[0] if output else "Unassigned"
        except (IndexError, RuntimeError):
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
            output = self._run(["ip", "route", "show", "dev", interface, "default"])
            return output.split()[2] if output else "None"
        except (IndexError, RuntimeError):
            return "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        try:
            with open("/etc/resolv.conf") as f:
                return [line.split()[1] for line in f if line.startswith("nameserver")]
        except FileNotFoundError:
            return []
