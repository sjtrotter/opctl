from unittest.mock import MagicMock, patch
from opctl.infrastructure.linux.backend import LinuxBackend
from opctl.domain.models.backend import BackendConfig


def _make_backend(sys_p=None, net_p=None, fw_p=None):
    sys_p = sys_p or MagicMock()
    net_p = net_p or MagicMock()
    fw_p = fw_p or MagicMock()

    with patch("opctl.infrastructure.linux.backend.resolve_provider",
               side_effect=[sys_p, net_p, fw_p]):
        backend = LinuxBackend(BackendConfig())

    return backend, sys_p, net_p, fw_p


class TestLinuxBackendDelegation:

    def test_set_hostname_delegates_to_system_provider(self):
        backend, sys_p, _, _ = _make_backend()
        backend.set_hostname("ops-box")
        sys_p.set_hostname.assert_called_once_with("ops-box")

    def test_get_hostname_delegates_to_system_provider(self):
        backend, sys_p, _, _ = _make_backend()
        sys_p.get_hostname.return_value = "ops-box"
        assert backend.get_hostname() == "ops-box"

    def test_configure_static_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        backend.configure_static("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        net_p.configure_static.assert_called_once_with("eth0", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])

    def test_configure_dhcp_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        backend.configure_dhcp("eth0")
        net_p.configure_dhcp.assert_called_once_with("eth0")

    def test_get_available_interfaces_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        net_p.get_available_interfaces.return_value = ["eth0", "wlan0"]
        assert backend.get_available_interfaces() == ["eth0", "wlan0"]

    def test_apply_ipv4_blocks_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        fw_p.apply_ipv4_blocks.assert_called_once_with(["10.0.0.0/8"], [], None)

    def test_apply_ipv4_allows_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.apply_ipv4_allows(["192.168.1.0/24"], [], "eth0")
        fw_p.apply_ipv4_allows.assert_called_once_with(["192.168.1.0/24"], [], "eth0")

    def test_apply_ipv6_blocks_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.apply_ipv6_blocks(["2001:db8::/32"], [], None)
        fw_p.apply_ipv6_blocks.assert_called_once_with(["2001:db8::/32"], [], None)

    def test_flush_managed_rules_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.flush_managed_rules()
        fw_p.flush_managed_rules.assert_called_once()

    def test_set_mac_address_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        backend.set_mac_address("eth0", "aa:bb:cc:dd:ee:ff")
        net_p.set_mac_address.assert_called_once_with("eth0", "aa:bb:cc:dd:ee:ff")

    def test_set_link_state_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        backend.set_link_state("eth0", "up")
        net_p.set_link_state.assert_called_once_with("eth0", "up")
