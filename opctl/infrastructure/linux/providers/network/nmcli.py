import os
import shutil
from typing import List
from opctl.domain.interfaces import INetworkAdapter, IProvider
from .._base import LinuxProvider


class NmcliProvider(LinuxProvider, INetworkAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "nmcli"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("nmcli") is not None

    def get_available_interfaces(self) -> List[str]:
        try:
            return [i for i in os.listdir("/sys/class/net/") if i != "lo"]
        except FileNotFoundError:
            return []

    def set_link_state(self, interface: str, state: str) -> None:
        self.validate_interface(interface)
        action = "connect" if state.lower() == "up" else "disconnect"
        self._run(["nmcli", "device", action, interface])

    def set_mac_address(self, interface: str, mac: str) -> None:
        self.validate_interface(interface)
        self.validate_mac(mac)
        self._run(["nmcli", "connection", "modify", interface,
                   "802-3-ethernet.cloned-mac-address", mac])
        self._run(["nmcli", "device", "reapply", interface])

    def get_mac_address(self, interface: str) -> str:
        try:
            with open(f"/sys/class/net/{interface}/address") as f:
                return f.read().strip().upper()
        except FileNotFoundError:
            return "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str, dns_servers: List[str]) -> None:
        self.validate_interface(interface)
        self.validate_ip(ip)
        if gateway:
            self.validate_ip(gateway)
        for dns in dns_servers:
            self.validate_dns(dns)
        self._run(["nmcli", "connection", "modify", interface,
                   "ipv4.method", "manual",
                   "ipv4.addresses", ip,
                   "ipv4.gateway", gateway or "",
                   "ipv4.dns", ",".join(dns_servers)])
        self._run(["nmcli", "connection", "up", interface])

    def configure_dhcp(self, interface: str) -> None:
        self.validate_interface(interface)
        self._run(["nmcli", "connection", "modify", interface, "ipv4.method", "auto"])
        self._run(["nmcli", "connection", "up", interface])

    def get_ip_address(self, interface: str) -> str:
        try:
            output = self._run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", interface])
            for line in output.splitlines():
                if line.startswith("IP4.ADDRESS"):
                    return line.split(":")[1].split("/")[0]
            return "Unassigned"
        except RuntimeError:
            return "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        try:
            output = self._run(["nmcli", "-t", "-f", "ipv4.method", "connection", "show", interface])
            return "auto" in output.lower()
        except Exception:
            return False

    def get_gateway(self, interface: str) -> str:
        try:
            output = self._run(["nmcli", "-t", "-f", "IP4.GATEWAY", "device", "show", interface])
            for line in output.splitlines():
                if line.startswith("IP4.GATEWAY"):
                    gw = line.split(":")[1].strip()
                    return gw if gw else "None"
            return "None"
        except RuntimeError:
            return "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        try:
            output = self._run(["nmcli", "-t", "-f", "IP4.DNS", "device", "show", interface])
            return [line.split(":")[1].strip() for line in output.splitlines()
                    if line.startswith("IP4.DNS")]
        except RuntimeError:
            return []
