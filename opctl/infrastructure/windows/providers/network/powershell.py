import shutil
from typing import List
from opctl.domain.interfaces import INetworkAdapter, IProvider
from .._base import WindowsProvider


class PowerShellNetworkProvider(WindowsProvider, INetworkAdapter, IProvider):

    @classmethod
    def provider_name(cls) -> str:
        return "powershell"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("powershell") is not None

    def get_available_interfaces(self) -> List[str]:
        output = self._run_ps("(Get-NetAdapter).Name")
        return [l.strip() for l in output.split("\n") if l.strip()] if output else []

    def set_link_state(self, interface: str, state: str) -> None:
        self.validate_interface(interface)
        action = "Enable-NetAdapter" if state.lower() == "up" else "Disable-NetAdapter"
        self._run_ps(f'{action} -Name "{interface}" -Confirm:$false')

    def set_mac_address(self, interface: str, mac: str) -> None:
        self.validate_interface(interface)
        self.validate_mac(mac)
        clean = mac.replace(":", "").replace("-", "")
        self._run_ps(f'Set-NetAdapter -Name "{interface}" -MacAddress "{clean}" -Confirm:$false')

    def get_mac_address(self, interface: str) -> str:
        self.validate_interface(interface)
        mac = self._run_ps(f'(Get-NetAdapter -Name "{interface}").MacAddress')
        return mac.replace("-", ":") if mac else "Unknown"

    def configure_static(self, interface: str, ip: str, gateway: str,
                         dns_servers: List[str]) -> None:
        self.validate_interface(interface)
        self.validate_ip(ip)
        if gateway:
            self.validate_ip(gateway)
        for dns in dns_servers:
            self.validate_dns(dns)
        prefix = 24
        if "/" in ip:
            ip, prefix = ip.split("/")
            prefix = int(prefix)
        self._run_ps(f'Remove-NetIPAddress -InterfaceAlias "{interface}" -Confirm:$false '
                     f'-ErrorAction SilentlyContinue')
        cmd = (f'New-NetIPAddress -InterfaceAlias "{interface}" '
               f'-IPAddress "{ip}" -PrefixLength {prefix}')
        if gateway:
            cmd += f' -DefaultGateway "{gateway}"'
        self._run_ps(cmd)
        if dns_servers:
            dns_str = ",".join(f'"{d}"' for d in dns_servers)
            self._run_ps(f'Set-DnsClientServerAddress -InterfaceAlias "{interface}" '
                         f'-ServerAddresses {dns_str}')

    def configure_dhcp(self, interface: str) -> None:
        self.validate_interface(interface)
        self._run_ps(f'Set-NetIPInterface -InterfaceAlias "{interface}" -Dhcp Enabled')
        self._run_ps(f'Set-DnsClientServerAddress -InterfaceAlias "{interface}" '
                     f'-ResetServerAddresses')

    def get_ip_address(self, interface: str) -> str:
        ip = self._run_ps(f'(Get-NetIPAddress -InterfaceAlias "{interface}" '
                          f'-AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress')
        return ip.split("\n")[0].strip() if ip else "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        output = self._run_ps(f'(Get-NetIPInterface -InterfaceAlias "{interface}" '
                              f'-AddressFamily IPv4).Dhcp')
        return output.strip().lower() == "enabled"

    def get_gateway(self, interface: str) -> str:
        gw = self._run_ps(f'(Get-NetRoute -InterfaceAlias "{interface}" '
                          f'-DestinationPrefix "0.0.0.0/0" '
                          f'-ErrorAction SilentlyContinue).NextHop')
        return gw if gw else "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        output = self._run_ps(f'(Get-DnsClientServerAddress -InterfaceAlias "{interface}" '
                              f'-AddressFamily IPv4).ServerAddresses')
        return [l.strip() for l in output.split("\n") if l.strip()] if output else []
