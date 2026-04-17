"""
Security tests — input validation hardening (issue #13).

These tests verify that malicious user input is rejected before reaching any
subprocess call or file write. Tests are organized by vulnerability class.
"""
import pytest
from unittest.mock import MagicMock, mock_open, patch

from opctl.infrastructure.validators import (
    validate_hostname, validate_mac, validate_ip,
    validate_dns, validate_interface, validate_port,
)

# Windows providers
from opctl.infrastructure.windows.providers.system.powershell import PowerShellSystemProvider
from opctl.infrastructure.windows.providers.system.wmic import WmicSystemProvider
from opctl.infrastructure.windows.providers.network.powershell import PowerShellNetworkProvider
from opctl.infrastructure.windows.providers.network.netsh import NetshNetworkProvider

# Linux providers
from opctl.infrastructure.linux.providers.system.hostnamectl import HostnamectlProvider
from opctl.infrastructure.linux.providers.system.hostname import HostnameProvider
from opctl.infrastructure.linux.providers.network.iproute2 import Iproute2Provider
from opctl.infrastructure.linux.providers.network.ifconfig import IfconfigProvider
from opctl.infrastructure.linux.providers.network.nmcli import NmcliProvider


def _win_ps(cls):
    p = cls.__new__(cls)
    p._run_ps = MagicMock(return_value="")
    return p


def _win_cmd(cls):
    p = cls.__new__(cls)
    p._run_cmd = MagicMock(return_value="")
    return p


def _linux(cls):
    p = cls.__new__(cls)
    p._run = MagicMock(return_value="")
    return p


# ---------------------------------------------------------------------------
# Validator unit tests
# ---------------------------------------------------------------------------

class TestValidateHostname:

    def test_valid_simple(self):
        assert validate_hostname("ops-box") == "ops-box"

    def test_valid_fqdn(self):
        assert validate_hostname("host.domain.mil") == "host.domain.mil"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_hostname("")

    def test_rejects_semicolon_injection(self):
        with pytest.raises(ValueError):
            validate_hostname("host; net user attacker pass /add")

    def test_rejects_ampersand_injection(self):
        with pytest.raises(ValueError):
            validate_hostname("host & calc")

    def test_rejects_pipe_injection(self):
        with pytest.raises(ValueError):
            validate_hostname("host | whoami")

    def test_rejects_powershell_subexpression(self):
        with pytest.raises(ValueError):
            validate_hostname('host$(Start-Process calc)')

    def test_rejects_double_quote_breakout(self):
        with pytest.raises(ValueError):
            validate_hostname('test" -Force; Stop-Process -Name explorer; echo "')

    def test_rejects_newline_injection(self):
        with pytest.raises(ValueError):
            validate_hostname("host\nnameserver 8.8.8.8")

    def test_rejects_label_too_long(self):
        with pytest.raises(ValueError):
            validate_hostname("a" * 64 + ".example.com")

    def test_rejects_hostname_too_long(self):
        with pytest.raises(ValueError):
            validate_hostname("a" * 254)

    def test_rejects_label_starting_with_hyphen(self):
        with pytest.raises(ValueError):
            validate_hostname("-badlabel.example.com")


class TestValidateMac:

    def test_valid_colon_format(self):
        assert validate_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_valid_dash_format(self):
        assert validate_mac("AA-BB-CC-DD-EE-FF") == "AA-BB-CC-DD-EE-FF"

    def test_rejects_injection_via_semicolon(self):
        with pytest.raises(ValueError):
            validate_mac("aa:bb:cc:dd:ee:ff; net user attacker /add")

    def test_rejects_short_mac(self):
        with pytest.raises(ValueError):
            validate_mac("aa:bb:cc:dd:ee")

    def test_rejects_non_hex(self):
        with pytest.raises(ValueError):
            validate_mac("gg:bb:cc:dd:ee:ff")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_mac("")


class TestValidateIp:

    def test_valid_ipv4(self):
        assert validate_ip("10.0.0.1") == "10.0.0.1"

    def test_valid_cidr(self):
        assert validate_ip("192.168.0.0/24") == "192.168.0.0/24"

    def test_valid_ipv6(self):
        assert validate_ip("2001:db8::1") == "2001:db8::1"

    def test_rejects_semicolon_injection(self):
        with pytest.raises(ValueError):
            validate_ip("10.0.0.1; ipconfig")

    def test_rejects_pipe_injection(self):
        with pytest.raises(ValueError):
            validate_ip("10.0.0.1 | whoami")

    def test_rejects_arbitrary_string(self):
        with pytest.raises(ValueError):
            validate_ip("not-an-ip")

    def test_rejects_netsh_injection_via_ip(self):
        with pytest.raises(ValueError):
            validate_ip("10.0.0.1 & net user attacker /add")


class TestValidateDns:

    def test_valid_dns(self):
        assert validate_dns("8.8.8.8") == "8.8.8.8"

    def test_rejects_newline_injection(self):
        with pytest.raises(ValueError):
            validate_dns("8.8.8.8\noptions timeout:0")

    def test_rejects_non_ip(self):
        with pytest.raises(ValueError):
            validate_dns("not-a-dns")


class TestValidateInterface:

    def test_valid_linux_name(self):
        assert validate_interface("eth0") == "eth0"

    def test_valid_windows_name_with_space(self):
        assert validate_interface("Local Area Connection") == "Local Area Connection"

    def test_rejects_semicolon(self):
        with pytest.raises(ValueError):
            validate_interface('eth0"; net user attacker /add; echo "')

    def test_rejects_ampersand(self):
        with pytest.raises(ValueError):
            validate_interface("eth0 & ipconfig > C:\\out.txt")

    def test_rejects_pipe(self):
        with pytest.raises(ValueError):
            validate_interface("eth0 | whoami")

    def test_rejects_shell_backtick(self):
        with pytest.raises(ValueError):
            validate_interface("eth0`whoami`")

    def test_rejects_dollar_sign(self):
        with pytest.raises(ValueError):
            validate_interface("eth0$(calc)")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_interface("")


class TestValidatePort:

    def test_valid_port(self):
        assert validate_port(443) == 443
        assert validate_port("80") == 80

    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            validate_port(0)

    def test_rejects_too_high(self):
        with pytest.raises(ValueError):
            validate_port(65536)

    def test_rejects_string_injection(self):
        with pytest.raises(ValueError):
            validate_port("80; del /f /q *.*")


# ---------------------------------------------------------------------------
# Windows provider — validation fires before subprocess
# ---------------------------------------------------------------------------

class TestWindowsProviderValidation:

    def test_ps_system_rejects_malicious_hostname(self):
        p = _win_ps(PowerShellSystemProvider)
        with pytest.raises(ValueError):
            p.set_hostname('test" -Force; Stop-Process -Name explorer; echo "')
        p._run_ps.assert_not_called()

    def test_ps_system_rejects_hostname_with_semicolon(self):
        p = _win_ps(PowerShellSystemProvider)
        with pytest.raises(ValueError):
            p.set_hostname("host; calc")
        p._run_ps.assert_not_called()

    def test_wmic_rejects_malicious_hostname(self):
        p = _win_cmd(WmicSystemProvider)
        with patch("socket.gethostname", return_value="current"):
            with pytest.raises(ValueError):
                p.set_hostname('"test"; taskkill /F /IM explorer.exe; echo "')
        p._run_cmd.assert_not_called()

    def test_ps_network_rejects_malicious_interface(self):
        p = _win_ps(PowerShellNetworkProvider)
        with pytest.raises(ValueError):
            p.set_link_state('Ethernet"; New-Item C:\\pwned; echo "', "up")
        p._run_ps.assert_not_called()

    def test_ps_network_rejects_malicious_mac(self):
        p = _win_ps(PowerShellNetworkProvider)
        with pytest.raises(ValueError):
            p.set_mac_address("Ethernet", "aa:bb:cc:dd:ee:ff; calc")
        p._run_ps.assert_not_called()

    def test_ps_network_rejects_malicious_ip(self):
        p = _win_ps(PowerShellNetworkProvider)
        with pytest.raises(ValueError):
            p.configure_static("Ethernet", "10.0.0.1 & ipconfig", "", [])
        p._run_ps.assert_not_called()

    def test_ps_network_rejects_malicious_dns(self):
        p = _win_ps(PowerShellNetworkProvider)
        with pytest.raises(ValueError):
            p.configure_static("Ethernet", "10.0.0.1/24", "", ["8.8.8.8\noptions ndots:0"])
        p._run_ps.assert_not_called()

    def test_netsh_rejects_malicious_interface(self):
        p = _win_cmd(NetshNetworkProvider)
        with pytest.raises(ValueError):
            p.set_link_state('LAN" & net user attacker /add & echo "', "up")
        p._run_cmd.assert_not_called()

    def test_netsh_rejects_malicious_ip_in_static(self):
        p = _win_cmd(NetshNetworkProvider)
        with pytest.raises(ValueError):
            p.configure_static("LAN", "10.0.0.1 & ipconfig", "", [])
        p._run_cmd.assert_not_called()

    def test_netsh_rejects_malicious_dns_injection(self):
        p = _win_cmd(NetshNetworkProvider)
        with pytest.raises(ValueError):
            p.configure_static("LAN", "10.0.0.1/24", "", ["127.0.0.1 & net user attacker /add"])
        p._run_cmd.assert_not_called()

    def test_ps_network_valid_inputs_reach_subprocess(self):
        p = _win_ps(PowerShellNetworkProvider)
        p.configure_static("Ethernet", "10.0.0.5/24", "10.0.0.1", ["8.8.8.8"])
        assert p._run_ps.called

    def test_netsh_valid_inputs_reach_subprocess(self):
        p = _win_cmd(NetshNetworkProvider)
        p.configure_static("Local Area Connection", "192.168.1.10/24", "192.168.1.1", ["8.8.8.8"])
        assert p._run_cmd.called

    # Read-only methods also pass interface name to _run_ps/_run_cmd
    def test_ps_get_ip_address_rejects_malicious_interface(self):
        p = _win_ps(PowerShellNetworkProvider)
        result = p.get_ip_address('Ethernet"; Start-Process calc; echo "')
        assert result == "Unassigned"
        p._run_ps.assert_not_called()

    def test_ps_is_dhcp_enabled_rejects_malicious_interface(self):
        p = _win_ps(PowerShellNetworkProvider)
        result = p.is_dhcp_enabled('Ethernet$(whoami)')
        assert result is False
        p._run_ps.assert_not_called()

    def test_ps_get_gateway_rejects_malicious_interface(self):
        p = _win_ps(PowerShellNetworkProvider)
        result = p.get_gateway('eth0 | ipconfig')
        assert result == "None"
        p._run_ps.assert_not_called()

    def test_ps_get_dns_servers_rejects_malicious_interface(self):
        p = _win_ps(PowerShellNetworkProvider)
        result = p.get_dns_servers('eth0; calc')
        assert result == []
        p._run_ps.assert_not_called()

    def test_netsh_get_ip_address_rejects_malicious_interface(self):
        p = _win_cmd(NetshNetworkProvider)
        result = p.get_ip_address('LAN" & ipconfig > C:\\out.txt & echo "')
        assert result == "Unassigned"
        p._run_cmd.assert_not_called()

    def test_netsh_get_gateway_rejects_malicious_interface(self):
        p = _win_cmd(NetshNetworkProvider)
        result = p.get_gateway('LAN & net user attacker /add')
        assert result == "None"
        p._run_cmd.assert_not_called()

    def test_netsh_get_dns_servers_rejects_malicious_interface(self):
        p = _win_cmd(NetshNetworkProvider)
        result = p.get_dns_servers('LAN | whoami')
        assert result == []
        p._run_cmd.assert_not_called()


# ---------------------------------------------------------------------------
# Linux provider — validation fires before _run and file writes
# ---------------------------------------------------------------------------

class TestLinuxProviderValidation:

    def test_hostnamectl_rejects_malicious_hostname(self):
        p = _linux(HostnamectlProvider)
        with pytest.raises(ValueError):
            p.set_hostname("host; rm -rf /")
        p._run.assert_not_called()

    def test_hostname_provider_rejects_malicious_hostname(self):
        p = _linux(HostnameProvider)
        with pytest.raises(ValueError):
            p.set_hostname("host\nnameserver 8.8.8.8")
        p._run.assert_not_called()

    def test_hostname_provider_rejects_malicious_hostname_no_file_write(self):
        p = _linux(HostnameProvider)
        m = mock_open()
        with patch("builtins.open", m):
            with pytest.raises(ValueError):
                p.set_hostname("host; rm -rf /")
        m.assert_not_called()

    def test_iproute2_rejects_malicious_interface(self):
        p = _linux(Iproute2Provider)
        with pytest.raises(ValueError):
            p.set_link_state("eth0; rm -rf /", "up")
        p._run.assert_not_called()

    def test_iproute2_rejects_malicious_mac(self):
        p = _linux(Iproute2Provider)
        with pytest.raises(ValueError):
            p.set_mac_address("eth0", "aa:bb:cc:dd:ee:ff; id")
        p._run.assert_not_called()

    def test_iproute2_rejects_malicious_ip_in_static(self):
        p = _linux(Iproute2Provider)
        with pytest.raises(ValueError):
            p.configure_static("eth0", "10.0.0.1; id", "", [])
        p._run.assert_not_called()

    def test_iproute2_rejects_dns_newline_injection(self):
        """Prevent nameserver 8.8.8.8\\noptions timeout:0 being written to resolv.conf."""
        p = _linux(Iproute2Provider)
        with pytest.raises(ValueError):
            p.configure_static("eth0", "10.0.0.1/24", "", ["8.8.8.8\noptions timeout:0"])
        p._run.assert_not_called()

    def test_iproute2_valid_inputs_reach_subprocess(self):
        p = _linux(Iproute2Provider)
        with patch("builtins.open", mock_open()):
            p.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        assert p._run.called

    def test_ifconfig_rejects_malicious_interface(self):
        p = _linux(IfconfigProvider)
        with pytest.raises(ValueError):
            p.configure_dhcp("eth0 | whoami")
        p._run.assert_not_called()

    def test_ifconfig_rejects_dns_injection_no_file_write(self):
        p = _linux(IfconfigProvider)
        m = mock_open()
        with patch("builtins.open", m):
            with pytest.raises(ValueError):
                p.configure_static("eth0", "10.0.0.1/24", "", ["1.1.1.1\nnameserver 8.8.8.8"])
        m.assert_not_called()

    def test_nmcli_rejects_malicious_interface(self):
        p = _linux(NmcliProvider)
        with pytest.raises(ValueError):
            p.set_link_state("eth0`whoami`", "up")
        p._run.assert_not_called()

    def test_nmcli_rejects_malicious_mac(self):
        p = _linux(NmcliProvider)
        with pytest.raises(ValueError):
            p.set_mac_address("eth0", "invalid-mac-injection")
        p._run.assert_not_called()

    def test_nmcli_rejects_malicious_ip(self):
        p = _linux(NmcliProvider)
        with pytest.raises(ValueError):
            p.configure_static("eth0", "not_an_ip", "", [])
        p._run.assert_not_called()

    def test_nmcli_valid_inputs_reach_subprocess(self):
        p = _linux(NmcliProvider)
        p.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        assert p._run.called


# ---------------------------------------------------------------------------
# Linux list-form immunity — shell injection is structurally impossible
# ---------------------------------------------------------------------------

class TestLinuxListFormImmunity:
    """
    Linux _run() uses subprocess list form (no shell=True), so even if a
    malicious string somehow bypassed validation it would be passed as a
    literal argument to the program, not interpreted by the shell.
    These tests document that invariant and verify the list structure.
    """

    def test_hostnamectl_passes_hostname_as_single_list_element(self):
        p = _linux(HostnamectlProvider)
        p.set_hostname("ops-box")
        cmd = p._run.call_args[0][0]
        assert isinstance(cmd, list)
        assert cmd == ["hostnamectl", "set-hostname", "ops-box"]
        assert len(cmd) == 3

    def test_iproute2_link_state_up_is_single_list_element(self):
        p = _linux(Iproute2Provider)
        p.set_link_state("eth0", "up")
        cmd = p._run.call_args[0][0]
        assert isinstance(cmd, list)
        assert "eth0" in cmd
        assert "up" in cmd

    def test_iproute2_mac_is_single_list_element(self):
        p = _linux(Iproute2Provider)
        p.set_mac_address("eth0", "aa:bb:cc:dd:ee:ff")
        cmd = p._run.call_args[0][0]
        assert isinstance(cmd, list)
        assert "aa:bb:cc:dd:ee:ff" in cmd
