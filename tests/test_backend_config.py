from opctl.domain.models.backend import BackendConfig
from opctl.domain.models.profile import OpProfile


class TestBackendConfig:

    def test_defaults(self):
        cfg = BackendConfig()
        assert cfg.firewall_provider == "auto"
        assert cfg.network_provider == "auto"
        assert cfg.system_provider == "auto"

    def test_to_dict(self):
        cfg = BackendConfig(firewall_provider="iptables", network_provider="nmcli", system_provider="hostnamectl")
        d = cfg.to_dict()
        assert d == {
            "firewall_provider": "iptables",
            "network_provider": "nmcli",
            "system_provider": "hostnamectl",
        }

    def test_round_trip_defaults(self):
        cfg = BackendConfig()
        d = cfg.to_dict()
        profile = OpProfile.from_dict({"backend": d})
        assert profile.backend.firewall_provider == "auto"
        assert profile.backend.network_provider == "auto"
        assert profile.backend.system_provider == "auto"

    def test_round_trip_explicit_values(self):
        original = BackendConfig(firewall_provider="ufw", network_provider="iproute2", system_provider="hostname")
        profile = OpProfile.from_dict({"backend": original.to_dict()})
        assert profile.backend.firewall_provider == "ufw"
        assert profile.backend.network_provider == "iproute2"
        assert profile.backend.system_provider == "hostname"

    def test_op_profile_to_dict_includes_backend(self):
        profile = OpProfile.from_dict({"backend": {"firewall_provider": "netsh"}})
        d = profile.to_dict()
        assert "backend" in d
        assert d["backend"]["firewall_provider"] == "netsh"

    def test_missing_backend_key_falls_back_to_auto(self):
        profile = OpProfile.from_dict({})
        assert profile.backend.firewall_provider == "auto"
        assert profile.backend.network_provider == "auto"
        assert profile.backend.system_provider == "auto"

    def test_partial_backend_key_inherits_defaults(self):
        profile = OpProfile.from_dict({"backend": {"firewall_provider": "powershell"}})
        assert profile.backend.firewall_provider == "powershell"
        assert profile.backend.network_provider == "auto"
        assert profile.backend.system_provider == "auto"
