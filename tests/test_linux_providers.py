import tempfile
import os
from unittest.mock import MagicMock, patch, mock_open
import pytest

from opctl.infrastructure.linux.providers.system.hostnamectl import HostnamectlProvider
from opctl.infrastructure.linux.providers.system.hostname import HostnameProvider
from opctl.infrastructure.linux.providers.network.iproute2 import Iproute2Provider
from opctl.infrastructure.linux.providers.network.ifconfig import IfconfigProvider
from opctl.infrastructure.linux.providers.network.nmcli import NmcliProvider
from opctl.infrastructure.linux.providers.firewall.iptables import IptablesProvider
from opctl.infrastructure.linux.providers.firewall.firewalld import FirewalldProvider
from opctl.infrastructure.linux.providers.firewall.ufw import UfwProvider


def _mock_run(cls):
    p = cls.__new__(cls)
    p._run = MagicMock(return_value="")
    return p


# ---------------------------------------------------------------------------
# System providers
# ---------------------------------------------------------------------------

class TestHostnamectlProvider:

    def test_set_hostname(self):
        p = _mock_run(HostnamectlProvider)
        p.set_hostname("ops-box")
        p._run.assert_called_once_with(["hostnamectl", "set-hostname", "ops-box"])

    def test_provider_name(self):
        assert HostnamectlProvider.provider_name() == "hostnamectl"


class TestHostnameProvider:

    def test_set_hostname_calls_command(self):
        p = _mock_run(HostnameProvider)
        with patch("builtins.open", mock_open()):
            p.set_hostname("ops-box")
        p._run.assert_called_once_with(["hostname", "ops-box"])

    def test_set_hostname_writes_etc_hostname(self):
        p = _mock_run(HostnameProvider)
        m = mock_open()
        with patch("builtins.open", m):
            p.set_hostname("ops-box")
        m.assert_called_once_with("/etc/hostname", "w")
        m().write.assert_called_once_with("ops-box\n")

    def test_set_hostname_tolerates_permission_error(self):
        p = _mock_run(HostnameProvider)
        with patch("builtins.open", side_effect=PermissionError):
            p.set_hostname("ops-box")
        p._run.assert_called_once()

    def test_provider_name(self):
        assert HostnameProvider.provider_name() == "hostname"


# ---------------------------------------------------------------------------
# Network providers — iproute2
# ---------------------------------------------------------------------------

class TestIproute2Provider:

    def test_configure_static_flushes_then_adds(self):
        p = _mock_run(Iproute2Provider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        calls = [c[0][0] for c in p._run.call_args_list]
        assert ["ip", "addr", "flush", "dev", "eth0"] in calls
        assert ["ip", "addr", "add", "10.0.0.1/24", "dev", "eth0"] in calls

    def test_configure_static_adds_gateway(self):
        p = _mock_run(Iproute2Provider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "10.0.0.1/24", "10.0.0.1", [])
        calls = [c[0][0] for c in p._run.call_args_list]
        assert ["ip", "route", "add", "default", "via", "10.0.0.1", "dev", "eth0"] in calls

    def test_configure_static_skips_gateway_when_empty(self):
        p = _mock_run(Iproute2Provider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "10.0.0.1/24", "", [])
        calls = [c[0][0] for c in p._run.call_args_list]
        assert not any("route" in c for c in calls)

    def test_configure_static_writes_resolv_conf(self):
        p = _mock_run(Iproute2Provider)
        m = mock_open()
        with patch("builtins.open", m):
            p.configure_static("eth0", "10.0.0.1/24", "", ["8.8.8.8"])
        written = "".join(call.args[0] for call in m().write.call_args_list)
        assert "nameserver 8.8.8.8" in written

    def test_configure_dhcp_calls_dhclient(self):
        p = _mock_run(Iproute2Provider)
        p.configure_dhcp("eth0")
        calls = [c[0][0] for c in p._run.call_args_list]
        assert ["dhclient", "eth0"] in calls

    def test_set_link_state_up(self):
        p = _mock_run(Iproute2Provider)
        p.set_link_state("eth0", "up")
        p._run.assert_called_once_with(["ip", "link", "set", "eth0", "up"])

    def test_set_link_state_down(self):
        p = _mock_run(Iproute2Provider)
        p.set_link_state("eth0", "down")
        p._run.assert_called_once_with(["ip", "link", "set", "eth0", "down"])

    def test_get_ip_address_parses_output(self):
        p = _mock_run(Iproute2Provider)
        p._run.return_value = "2: eth0    inet 10.0.0.5/24 brd 10.0.0.255 scope global eth0"
        assert p.get_ip_address("eth0") == "10.0.0.5"

    def test_get_ip_address_returns_unassigned_on_empty(self):
        p = _mock_run(Iproute2Provider)
        p._run.return_value = ""
        assert p.get_ip_address("eth0") == "Unassigned"

    def test_provider_name(self):
        assert Iproute2Provider.provider_name() == "iproute2"


# ---------------------------------------------------------------------------
# Network providers — ifconfig
# ---------------------------------------------------------------------------

class TestIfconfigProvider:

    def test_configure_static_generates_correct_netmask_24(self):
        p = _mock_run(IfconfigProvider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "192.168.1.5/24", "192.168.1.1", [])
        cmd = p._run.call_args_list[0][0][0]
        assert cmd == ["ifconfig", "eth0", "192.168.1.5", "netmask", "255.255.255.0", "up"]

    def test_configure_static_generates_correct_netmask_16(self):
        p = _mock_run(IfconfigProvider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "10.0.0.1/16", "", [])
        cmd = p._run.call_args_list[0][0][0]
        assert "255.255.0.0" in cmd

    def test_configure_dhcp_calls_dhclient(self):
        p = _mock_run(IfconfigProvider)
        p.configure_dhcp("eth0")
        calls = [c[0][0] for c in p._run.call_args_list]
        assert ["dhclient", "eth0"] in calls

    def test_get_ip_address_parses_inet(self):
        p = _mock_run(IfconfigProvider)
        p._run.return_value = "inet 192.168.1.10  netmask 255.255.255.0"
        assert p.get_ip_address("eth0") == "192.168.1.10"

    def test_provider_name(self):
        assert IfconfigProvider.provider_name() == "ifconfig"


# ---------------------------------------------------------------------------
# Network providers — nmcli
# ---------------------------------------------------------------------------

class TestNmcliProvider:

    def test_configure_static_calls_modify_and_up(self):
        p = _mock_run(NmcliProvider)
        p.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        calls = [c[0][0] for c in p._run.call_args_list]
        assert any("connection" in c and "modify" in c for c in calls)
        assert any("connection" in c and "up" in c for c in calls)

    def test_configure_static_passes_ip_and_gateway(self):
        p = _mock_run(NmcliProvider)
        p.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", [])
        cmd = p._run.call_args_list[0][0][0]
        assert "10.0.0.1/24" in cmd
        assert "10.0.0.254" in cmd

    def test_configure_dhcp(self):
        p = _mock_run(NmcliProvider)
        p.configure_dhcp("eth0")
        calls = [c[0][0] for c in p._run.call_args_list]
        assert any("auto" in c for c in calls)

    def test_set_link_state_up_calls_connect(self):
        p = _mock_run(NmcliProvider)
        p.set_link_state("eth0", "up")
        p._run.assert_called_once_with(["nmcli", "device", "connect", "eth0"])

    def test_set_link_state_down_calls_disconnect(self):
        p = _mock_run(NmcliProvider)
        p.set_link_state("eth0", "down")
        p._run.assert_called_once_with(["nmcli", "device", "disconnect", "eth0"])

    def test_get_ip_address_parses_output(self):
        p = _mock_run(NmcliProvider)
        p._run.return_value = "IP4.ADDRESS[1]:10.0.0.5/24"
        assert p.get_ip_address("eth0") == "10.0.0.5"

    def test_provider_name(self):
        assert NmcliProvider.provider_name() == "nmcli"


# ---------------------------------------------------------------------------
# Firewall providers — iptables
# ---------------------------------------------------------------------------

class TestIptablesProvider:

    def test_flush_flushes_chain(self):
        p = _mock_run(IptablesProvider)
        p.flush_managed_rules()
        p._run.assert_called_once_with(["iptables", "-F", "OPCTL_OUT"])

    def test_flush_creates_chain_on_error(self):
        p = _mock_run(IptablesProvider)
        p._run.side_effect = [RuntimeError("no chain"), None, None]
        p.flush_managed_rules()
        calls = [c[0][0] for c in p._run.call_args_list]
        assert ["iptables", "-N", "OPCTL_OUT"] in calls
        assert ["iptables", "-I", "OUTPUT", "1", "-j", "OPCTL_OUT"] in calls

    def test_apply_ipv4_blocks_adds_reject_rule(self):
        p = _mock_run(IptablesProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmd = p._run.call_args[0][0]
        assert "REJECT" in cmd
        assert "10.0.0.0/8" in cmd

    def test_apply_ipv4_allows_adds_accept_rule(self):
        p = _mock_run(IptablesProvider)
        p.apply_ipv4_allows(["192.168.1.0/24"], [], None)
        cmd = p._run.call_args[0][0]
        assert "ACCEPT" in cmd

    def test_apply_with_interface_adds_output_flag(self):
        p = _mock_run(IptablesProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], "eth0")
        cmd = p._run.call_args[0][0]
        assert "-o" in cmd
        assert "eth0" in cmd

    def test_apply_port_rules_generates_tcp_and_udp(self):
        p = _mock_run(IptablesProvider)
        p.apply_ipv4_blocks([], ["1.2.3.4:443"], None)
        cmds = [c[0][0] for c in p._run.call_args_list]
        assert any("tcp" in c for c in cmds)
        assert any("udp" in c for c in cmds)
        assert any("443" in c for c in cmds)

    def test_apply_ipv6_is_noop(self):
        p = _mock_run(IptablesProvider)
        p.apply_ipv6_blocks(["2001:db8::/32"], [], None)
        p._run.assert_not_called()

    def test_provider_name(self):
        assert IptablesProvider.provider_name() == "iptables"


# ---------------------------------------------------------------------------
# Firewall providers — firewalld
# ---------------------------------------------------------------------------

class TestFirewalldProvider:

    def test_flush_deletes_then_recreates_zone(self):
        p = _mock_run(FirewalldProvider)
        p.flush_managed_rules()
        cmds = [c[0][0] for c in p._run.call_args_list]
        assert any("--delete-zone=opctl" in c for c in cmds)
        assert any("--new-zone=opctl" in c for c in cmds)
        assert any("--reload" in c for c in cmds)

    def test_apply_ipv4_blocks_adds_reject_rich_rule(self):
        p = _mock_run(FirewalldProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmds = [" ".join(c[0][0]) for c in p._run.call_args_list]
        rule_calls = [c for c in cmds if "--add-rich-rule" in c]
        assert any("reject" in c for c in rule_calls)
        assert any("10.0.0.0/8" in c for c in rule_calls)

    def test_apply_ipv4_allows_adds_accept_rich_rule(self):
        p = _mock_run(FirewalldProvider)
        p.apply_ipv4_allows(["192.168.1.0/24"], [], None)
        cmds = [" ".join(c[0][0]) for c in p._run.call_args_list]
        rule_calls = [c for c in cmds if "--add-rich-rule" in c]
        assert any("accept" in c for c in rule_calls)

    def test_apply_reloads_after_adding_rules(self):
        p = _mock_run(FirewalldProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        last_cmd = p._run.call_args_list[-1][0][0]
        assert last_cmd == ["firewall-cmd", "--reload"]

    def test_apply_ipv6_uses_ipv6_family(self):
        p = _mock_run(FirewalldProvider)
        p.apply_ipv6_blocks(["2001:db8::/32"], [], None)
        cmds = [" ".join(c[0][0]) for c in p._run.call_args_list]
        rule_calls = [c for c in cmds if "--add-rich-rule" in c]
        assert any("ipv6" in c for c in rule_calls)

    def test_provider_name(self):
        assert FirewalldProvider.provider_name() == "firewalld"


# ---------------------------------------------------------------------------
# Firewall providers — ufw
# ---------------------------------------------------------------------------

class TestUfwProvider:

    def test_apply_ipv4_blocks_calls_deny(self):
        p = _mock_run(UfwProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmd = p._run.call_args[0][0]
        assert "deny" in cmd
        assert "10.0.0.0/8" in cmd

    def test_apply_ipv4_allows_calls_allow(self):
        p = _mock_run(UfwProvider)
        p.apply_ipv4_allows(["192.168.1.0/24"], [], None)
        cmd = p._run.call_args[0][0]
        assert "allow" in cmd

    def test_apply_adds_comment(self):
        p = _mock_run(UfwProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        cmd = p._run.call_args[0][0]
        assert "opctl" in cmd

    def test_apply_with_interface_includes_on_flag(self):
        p = _mock_run(UfwProvider)
        p.apply_ipv4_blocks(["10.0.0.0/8"], [], "eth0")
        cmd = p._run.call_args[0][0]
        assert "on" in cmd
        assert "eth0" in cmd

    def test_apply_port_rules_generate_tcp_and_udp(self):
        p = _mock_run(UfwProvider)
        p.apply_ipv4_blocks([], ["10.0.0.1:80"], None)
        cmds = [c[0][0] for c in p._run.call_args_list]
        assert any("tcp" in c for c in cmds)
        assert any("udp" in c for c in cmds)

    def test_flush_deletes_rules_by_comment_in_reverse(self):
        p = _mock_run(UfwProvider)
        p._run.return_value = (
            "Status: active\n"
            "[ 1] rule one  ALLOW OUT  ...\n"
            "[ 2] opctl-rule  DENY OUT  ... opctl\n"
            "[ 3] opctl-rule2  DENY OUT  ... opctl\n"
        )
        p.flush_managed_rules()
        delete_calls = [c[0][0] for c in p._run.call_args_list if "delete" in c[0][0]]
        # Should delete in reverse order (3 before 2)
        assert delete_calls[0] == ["ufw", "--force", "delete", "3"]
        assert delete_calls[1] == ["ufw", "--force", "delete", "2"]

    def test_flush_ignores_non_opctl_rules(self):
        p = _mock_run(UfwProvider)
        p._run.return_value = "[ 1] some-other-rule  ALLOW OUT  ...\n"
        p.flush_managed_rules()
        assert p._run.call_count == 1

    def test_provider_name(self):
        assert UfwProvider.provider_name() == "ufw"
