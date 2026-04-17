from unittest.mock import patch, MagicMock, call
import pytest

from opctl.infrastructure.windows.providers.system.powershell import PowerShellSystemProvider
from opctl.infrastructure.windows.providers.system.wmic import WmicSystemProvider
from opctl.infrastructure.windows.providers.network.powershell import PowerShellNetworkProvider
from opctl.infrastructure.windows.providers.network.netsh import NetshNetworkProvider
from opctl.infrastructure.windows.providers.firewall.powershell import PowerShellFirewallProvider
from opctl.infrastructure.windows.providers.firewall.netsh import NetshFirewallProvider


def _ps_provider(cls):
    """Return an instance with _run_ps mocked out."""
    p = cls.__new__(cls)
    p._run_ps = MagicMock(return_value="")
    return p


def _cmd_provider(cls):
    """Return an instance with _run_cmd mocked out."""
    p = cls.__new__(cls)
    p._run_cmd = MagicMock(return_value="")
    return p


# ---------------------------------------------------------------------------
# System providers
# ---------------------------------------------------------------------------

class TestPowerShellSystemProvider:

    def test_set_hostname(self):
        p = _ps_provider(PowerShellSystemProvider)
        p.set_hostname("ops-box")
        p._run_ps.assert_called_once()
        cmd = p._run_ps.call_args[0][0]
        assert "Rename-Computer" in cmd
        assert "ops-box" in cmd

    def test_provider_name(self):
        assert PowerShellSystemProvider.provider_name() == "powershell"


class TestWmicSystemProvider:

    def test_set_hostname(self):
        p = _cmd_provider(WmicSystemProvider)
        with patch("socket.gethostname", return_value="OLD"):
            p.set_hostname("NEW")
        p._run_cmd.assert_called_once()
        cmd = p._run_cmd.call_args[0][0]
        assert "wmic" in cmd
        assert "NEW" in cmd

    def test_provider_name(self):
        assert WmicSystemProvider.provider_name() == "wmic"


# ---------------------------------------------------------------------------
# Network providers — PowerShell
# ---------------------------------------------------------------------------

class TestPowerShellNetworkProvider:

    def test_get_available_interfaces_parses_output(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p._run_ps.return_value = "Ethernet\nWi-Fi\n"
        result = p.get_available_interfaces()
        assert result == ["Ethernet", "Wi-Fi"]

    def test_get_available_interfaces_empty_output(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p._run_ps.return_value = ""
        assert p.get_available_interfaces() == []

    def test_configure_static_calls_new_netipaddress(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p.configure_static("Ethernet", "10.0.0.5/24", "10.0.0.1", ["8.8.8.8"])
        calls = [str(c) for c in p._run_ps.call_args_list]
        full = " ".join(calls)
        assert "New-NetIPAddress" in full
        assert "10.0.0.5" in full

    def test_configure_static_sets_dns(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p.configure_static("Ethernet", "10.0.0.5/24", "10.0.0.1", ["8.8.8.8"])
        calls = [str(c) for c in p._run_ps.call_args_list]
        full = " ".join(calls)
        assert "Set-DnsClientServerAddress" in full
        assert "8.8.8.8" in full

    def test_configure_static_no_gateway_omits_it(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p.configure_static("Ethernet", "10.0.0.5/24", "", ["8.8.8.8"])
        calls = [str(c) for c in p._run_ps.call_args_list]
        full = " ".join(calls)
        assert "DefaultGateway" not in full

    def test_configure_dhcp(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p.configure_dhcp("Ethernet")
        calls = [str(c) for c in p._run_ps.call_args_list]
        full = " ".join(calls)
        assert "Dhcp" in full or "dhcp" in full.lower()

    def test_get_mac_address_replaces_dashes(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p._run_ps.return_value = "AA-BB-CC-DD-EE-FF"
        result = p.get_mac_address("Ethernet")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_get_mac_address_unknown_when_empty(self):
        p = _ps_provider(PowerShellNetworkProvider)
        p._run_ps.return_value = ""
        assert p.get_mac_address("Ethernet") == "Unknown"

    def test_provider_name(self):
        assert PowerShellNetworkProvider.provider_name() == "powershell"


# ---------------------------------------------------------------------------
# Network providers — netsh
# ---------------------------------------------------------------------------

class TestNetshNetworkProvider:

    def test_configure_static_generates_netmask(self):
        p = _cmd_provider(NetshNetworkProvider)
        p.configure_static("Local Area Connection", "192.168.1.10/24", "192.168.1.1", [])
        cmd = p._run_cmd.call_args_list[0][0][0]
        assert "255.255.255.0" in cmd

    def test_configure_static_prefix_16(self):
        p = _cmd_provider(NetshNetworkProvider)
        p.configure_static("LAN", "10.0.0.1/16", "", [])
        cmd = p._run_cmd.call_args_list[0][0][0]
        assert "255.255.0.0" in cmd

    def test_configure_static_adds_dns(self):
        p = _cmd_provider(NetshNetworkProvider)
        p.configure_static("LAN", "10.0.0.1/24", "", ["8.8.8.8", "1.1.1.1"])
        cmds = [c[0][0] for c in p._run_cmd.call_args_list]
        assert any("8.8.8.8" in c for c in cmds)
        assert any("1.1.1.1" in c for c in cmds)

    def test_get_mac_address_filters_by_interface(self):
        p = _cmd_provider(NetshNetworkProvider)
        # getmac /fo csv /nh /v output: "Connection Name","Adapter","Physical Address","Transport"
        p._run_cmd.return_value = (
            '"Wi-Fi","Wi-Fi Adapter","AA-BB-CC-DD-EE-FF","..."\n'
            '"Ethernet","Ethernet Adapter","11-22-33-44-55-66","..."'
        )
        result = p.get_mac_address("Ethernet")
        assert result == "11:22:33:44:55:66"

    def test_get_mac_address_case_insensitive(self):
        p = _cmd_provider(NetshNetworkProvider)
        p._run_cmd.return_value = '"ethernet","adapter","AA-BB-CC-DD-EE-FF","..."'
        result = p.get_mac_address("Ethernet")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_get_mac_address_unknown_when_not_found(self):
        p = _cmd_provider(NetshNetworkProvider)
        p._run_cmd.return_value = '"Wi-Fi","adapter","AA-BB-CC-DD-EE-FF","..."'
        result = p.get_mac_address("Ethernet")
        assert result == "Unknown"

    def test_configure_dhcp(self):
        p = _cmd_provider(NetshNetworkProvider)
        p.configure_dhcp("LAN")
        cmds = [c[0][0] for c in p._run_cmd.call_args_list]
        assert any("dhcp" in c for c in cmds)

    def test_provider_name(self):
        assert NetshNetworkProvider.provider_name() == "netsh"


# ---------------------------------------------------------------------------
# Firewall providers — PowerShell
# ---------------------------------------------------------------------------

class TestPowerShellFirewallProvider:

    def test_flush_managed_rules(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.flush_managed_rules()
        cmd = p._run_ps.call_args[0][0]
        assert "Remove-NetFirewallRule" in cmd
        assert "OpCtl" in cmd

    def test_apply_ipv4_blocks_calls_new_rule(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmd = p._run_ps.call_args[0][0]
        assert "New-NetFirewallRule" in cmd
        assert "Block" in cmd
        assert "10.0.0.0/8" in cmd

    def test_apply_ipv4_allows_calls_new_rule_allow(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.apply_ipv4_allows(["192.168.1.0/24"], [], None)
        cmd = p._run_ps.call_args[0][0]
        assert "Allow" in cmd

    def test_apply_blocks_with_interface(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], "Ethernet")
        cmd = p._run_ps.call_args[0][0]
        assert "Ethernet" in cmd

    def test_apply_port_rules_generates_tcp_and_udp(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.apply_ipv4_blocks([], ["10.0.0.1:443"], None)
        cmds = [c[0][0] for c in p._run_ps.call_args_list]
        assert any("TCP" in c for c in cmds)
        assert any("UDP" in c for c in cmds)

    def test_empty_cidr_list_makes_no_call(self):
        p = _ps_provider(PowerShellFirewallProvider)
        p.apply_ipv4_blocks([], [], None)
        p._run_ps.assert_not_called()

    def test_provider_name(self):
        assert PowerShellFirewallProvider.provider_name() == "powershell"


# ---------------------------------------------------------------------------
# Firewall providers — netsh
# ---------------------------------------------------------------------------

class TestNetshFirewallProvider:

    def test_apply_ipv4_blocks_generates_block_rule(self):
        p = _cmd_provider(NetshFirewallProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmd = p._run_cmd.call_args[0][0]
        assert "netsh advfirewall firewall add rule" in cmd
        assert "action=block" in cmd
        assert "10.0.0.0/8" in cmd

    def test_apply_ipv4_allows_generates_allow_rule(self):
        p = _cmd_provider(NetshFirewallProvider)
        p.apply_ipv4_allows(["192.168.0.0/16"], [], None)
        cmd = p._run_cmd.call_args[0][0]
        assert "action=allow" in cmd

    def test_rule_name_has_opctl_prefix(self):
        p = _cmd_provider(NetshFirewallProvider)
        p.apply_ipv4_blocks(["1.2.3.4/32"], [], None)
        cmd = p._run_cmd.call_args[0][0]
        assert 'name="opctl-' in cmd

    def test_port_rules_generate_tcp_and_udp(self):
        p = _cmd_provider(NetshFirewallProvider)
        p.apply_ipv4_blocks([], ["1.2.3.4:80"], None)
        cmds = [c[0][0] for c in p._run_cmd.call_args_list]
        assert any("tcp" in c for c in cmds)
        assert any("udp" in c for c in cmds)

    def test_flush_deletes_opctl_rules(self):
        p = _cmd_provider(NetshFirewallProvider)
        p._run_cmd.side_effect = [
            "Rule Name: opctl-v4drop-10.0.0.0/8\nDir: Out\n",
            "",
        ]
        p.flush_managed_rules()
        delete_call = p._run_cmd.call_args_list[1][0][0]
        assert "delete rule" in delete_call
        assert "opctl" in delete_call.lower()

    def test_flush_ignores_non_opctl_rules(self):
        p = _cmd_provider(NetshFirewallProvider)
        p._run_cmd.return_value = "Rule Name: SomeOtherRule\nDir: Out\n"
        p.flush_managed_rules()
        assert p._run_cmd.call_count == 1

    def test_provider_name(self):
        assert NetshFirewallProvider.provider_name() == "netsh"
