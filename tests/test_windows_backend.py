from unittest.mock import MagicMock, patch
from opctl.infrastructure.windows.backend import WindowsBackend
from opctl.domain.models.backend import BackendConfig


def _make_backend(sys_p=None, net_p=None, fw_p=None):
    """Build a WindowsBackend with mock providers injected via resolve_provider."""
    sys_p = sys_p or MagicMock()
    net_p = net_p or MagicMock()
    fw_p = fw_p or MagicMock()

    with patch("opctl.infrastructure.windows.backend.resolve_provider",
               side_effect=[sys_p, net_p, fw_p]):
        backend = WindowsBackend(BackendConfig())

    return backend, sys_p, net_p, fw_p


class TestWindowsBackendDelegation:

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
        backend.configure_static("Ethernet", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])
        net_p.configure_static.assert_called_once_with("Ethernet", "10.0.0.1/24", "10.0.0.254", ["8.8.8.8"])

    def test_configure_dhcp_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        backend.configure_dhcp("Ethernet")
        net_p.configure_dhcp.assert_called_once_with("Ethernet")

    def test_get_available_interfaces_delegates_to_network_provider(self):
        backend, _, net_p, _ = _make_backend()
        net_p.get_available_interfaces.return_value = ["Ethernet", "Wi-Fi"]
        assert backend.get_available_interfaces() == ["Ethernet", "Wi-Fi"]

    def test_apply_ipv4_blocks_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.apply_ipv4_blocks(["10.0.0.0/8"], [], None)
        fw_p.apply_ipv4_blocks.assert_called_once_with(["10.0.0.0/8"], [], None)

    def test_apply_ipv4_allows_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.apply_ipv4_allows(["192.168.1.0/24"], [], "Ethernet")
        fw_p.apply_ipv4_allows.assert_called_once_with(["192.168.1.0/24"], [], "Ethernet")

    def test_flush_managed_rules_delegates_to_firewall_provider(self):
        backend, _, _, fw_p = _make_backend()
        backend.flush_managed_rules()
        fw_p.flush_managed_rules.assert_called_once()

    def test_system_provider_does_not_receive_network_calls(self):
        backend, sys_p, _, _ = _make_backend()
        backend.configure_dhcp("Ethernet")
        assert not hasattr(sys_p, "configure_dhcp") or not sys_p.configure_dhcp.called

    def test_network_provider_does_not_receive_firewall_calls(self):
        backend, _, net_p, _ = _make_backend()
        backend.flush_managed_rules()
        assert not hasattr(net_p, "flush_managed_rules") or not net_p.flush_managed_rules.called
