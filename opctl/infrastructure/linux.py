import subprocess
import os
import socket
from typing import List
from opctl.domain.interfaces import ISystemAdapter, INetworkAdapter, IFirewallAdapter

class LinuxBackend(ISystemAdapter, INetworkAdapter, IFirewallAdapter):
    """Concrete implementation for Linux focusing on iproute2 and native sysfs."""

    def _run(self, cmd: List[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            raise RuntimeError(f"Linux Command Error: {error_msg}\nCommand: {' '.join(cmd)}")

    # --- ISystemAdapter ---
    def set_hostname(self, hostname: str) -> None:
        self._run(["hostnamectl", "set-hostname", hostname])

    def get_hostname(self) -> str:
        return socket.gethostname()

    # --- INetworkAdapter ---
    def get_available_interfaces(self) -> List[str]:
        try:
            return [iface for iface in os.listdir('/sys/class/net/') if iface != 'lo']
        except FileNotFoundError:
            return []

    def set_link_state(self, interface: str, state: str) -> None:
        self._run(["ip", "link", "set", interface, state.lower()])

    def set_mac_address(self, interface: str, mac: str) -> None:
        self._run(["ip", "link", "set", interface, "address", mac])

    def get_mac_address(self, interface: str) -> str:
        try:
            with open(f"/sys/class/net/{interface}/address", "r") as f:
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
        try:
            self._run(["dhclient", interface])
        except Exception:
            self._run(["nmcli", "device", "reapply", interface])

    def get_ip_address(self, interface: str) -> str:
        cmd = ["ip", "-4", "-o", "addr", "show", interface]
        try:
            output = self._run(cmd)
            return output.split()[3].split('/')[0] if output else "Unassigned"
        except (IndexError, RuntimeError):
            return "Unassigned"

    def is_dhcp_enabled(self, interface: str) -> bool:
        if any(os.path.exists(f"/var/lib/dhcp/dhclient.{interface}.leases") for interface in [interface]):
            return True
        try:
            ps = self._run(["ps", "ax"])
            if f"dhclient {interface}" in ps: return True
        except Exception: pass
        try:
            nm_mode = self._run(["nmcli", "-t", "-f", "ipv4.method", "dev", "show", interface])
            return "auto" in nm_mode.lower()
        except Exception: pass
        return False

    def get_gateway(self, interface: str) -> str:
        try:
            output = self._run(["ip", "route", "show", "dev", interface, "default"])
            return output.split()[2] if output else "None"
        except (IndexError, RuntimeError):
            return "None"

    def get_dns_servers(self, interface: str) -> List[str]:
        try:
            with open("/etc/resolv.conf", "r") as f:
                return [line.split()[1] for line in f if line.startswith("nameserver")]
        except FileNotFoundError:
            return []

    # --- IFirewallAdapter ---
    def flush_managed_rules(self) -> None:
        try:
            self._run(["iptables", "-F", "OPCTL_OUT"])
        except RuntimeError:
            self._run(["iptables", "-N", "OPCTL_OUT"])
            self._run(["iptables", "-I", "OUTPUT", "1", "-j", "OPCTL_OUT"])

    def _apply_rules(self, cidrs: List[str], ports: List[str], action: str) -> None:
        target = "REJECT" if action == "Block" else "ACCEPT"
        for cidr in cidrs:
            self._run(["iptables", "-A", "OPCTL_OUT", "-d", cidr, "-j", target])
        for entry in ports:
            if ":" not in entry: continue
            ip, port = entry.rsplit(":", 1)
            clean_ip = ip.replace("[", "").replace("]", "")
            for proto in ["tcp", "udp"]:
                self._run(["iptables", "-A", "OPCTL_OUT", "-p", proto, "-d", clean_ip, "--dport", port, "-j", target])

    def apply_ipv4_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_rules(cidrs, port_overrides, "Block")

    def apply_ipv4_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        self._apply_rules(cidrs, port_overrides, "Allow")

    def apply_ipv6_blocks(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass

    def apply_ipv6_allows(self, cidrs: List[str], port_overrides: List[str]) -> None:
        pass