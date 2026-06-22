from opctl.domain.services.playbook_validator import validate_playbook


class TestPlaybookValidator:

    def test_valid_playbook_has_no_errors(self):
        data = {
            "meta": {"name": "m", "version": 1, "description": "d"},
            "system": {"hostname": "recon-01", "unmanaged_policy": "isolate"},
            "network": {"global_dns": ["1.1.1.1"], "default_gateway": "10.0.0.1"},
            "ntp": {"servers": ["0.pool.ntp.org", "10.0.0.2"]},
            "interfaces": {"eth0": {
                "mode": "static", "mac_address": "AA:BB:CC:DD:EE:FF",
                "ip_addresses": ["10.10.0.5/24"], "gateway": "10.10.0.1", "dns_servers": ["1.1.1.1"],
                "policy": {"trusted": ["192.168.0.0/16"], "target": ["10.0.0.5:443"], "excluded": []}}},
            "global_policy": {"trusted": [], "target": ["192.168.*.10"], "excluded": ["10.0.0.0/8"]},
            "backend": {"firewall_provider": "iptables", "network_provider": "auto", "system_provider": "auto"},
        }
        assert validate_playbook(data) == []

    def test_empty_playbook_is_valid(self):
        assert validate_playbook({}) == []

    def test_bad_hostname(self):
        assert any("hostname" in e for e in validate_playbook({"system": {"hostname": "bad host!"}}))

    def test_bad_unmanaged_enum(self):
        assert any("unmanaged_policy" in e for e in validate_playbook({"system": {"unmanaged_policy": "nuke"}}))

    def test_bad_mode_enum(self):
        assert any("mode" in e for e in validate_playbook({"interfaces": {"eth0": {"mode": "warp"}}}))

    def test_bad_mac(self):
        assert any("mac_address" in e for e in validate_playbook({"interfaces": {"eth0": {"mac_address": "zz:zz"}}}))

    def test_bad_ip(self):
        assert any("ip_addresses" in e for e in
                   validate_playbook({"interfaces": {"eth0": {"ip_addresses": ["999.1.1.1/24"]}}}))

    def test_bad_dns(self):
        assert any("global_dns" in e for e in validate_playbook({"network": {"global_dns": ["nope"]}}))

    def test_bad_firewall_rule(self):
        assert any("trusted" in e for e in
                   validate_playbook({"global_policy": {"trusted": ["notanip"], "target": [], "excluded": []}}))

    def test_port_rule_is_valid(self):
        assert validate_playbook(
            {"global_policy": {"trusted": ["10.0.0.5:443"], "target": [], "excluded": []}}) == []

    def test_port_out_of_range_rejected(self):
        errs = validate_playbook({"global_policy": {"target": ["10.0.0.5:99999"], "trusted": [], "excluded": []}})
        assert any("port" in e.lower() for e in errs)

    def test_non_string_rule_reported(self):
        assert any("must be a string" in e for e in
                   validate_playbook({"global_policy": {"trusted": [123], "target": [], "excluded": []}}))

    def test_bad_provider(self):
        assert any("firewall_provider" in e for e in validate_playbook({"backend": {"firewall_provider": "bogus"}}))

    def test_bad_ntp_server(self):
        assert any("ntp.servers" in e for e in validate_playbook({"ntp": {"servers": ["bad host!"]}}))

    def test_meta_version_must_be_int(self):
        assert any("version" in e for e in validate_playbook({"meta": {"version": "two"}}))

    def test_collects_all_errors_at_once(self):
        errs = validate_playbook({
            "system": {"hostname": "bad!", "unmanaged_policy": "nuke"},
            "interfaces": {"eth0": {"mode": "warp", "mac_address": "zz"}},
            "backend": {"firewall_provider": "bogus"},
        })
        assert len(errs) >= 5

    def test_non_string_scalar_is_rejected_not_crash(self):
        # Regression: non-string scalars used to raise an uncaught TypeError mid-validation.
        errs = validate_playbook({"system": {"hostname": 123}, "backend": {"firewall_provider": "bogus"}})
        assert any("hostname" in e for e in errs)
        assert any("firewall_provider" in e for e in errs)  # collection still completes

    def test_integer_dns_is_rejected(self):
        # ipaddress.ip_address(123) == 0.0.0.123, so this must be caught explicitly.
        assert any("global_dns" in e for e in validate_playbook({"network": {"global_dns": [123]}}))

    def test_default_gateway_validated(self):
        assert any("default_gateway" in e for e in validate_playbook({"network": {"default_gateway": "notanip"}}))

    def test_ipv4_dash_and_splat_rules_valid(self):
        assert validate_playbook({"global_policy": {
            "trusted": ["192.168.0-5.10", "192.168.*.10:443"], "target": [], "excluded": []}}) == []

    def test_ipv6_cidr_and_port_rules_valid(self):
        assert validate_playbook({"global_policy": {
            "trusted": ["2001:db8::/32", "[2001:db8::1]:443"], "target": [], "excluded": []}}) == []

    def test_ipv6_splat_rule_rejected(self):
        assert any("trusted" in e for e in validate_playbook(
            {"global_policy": {"trusted": ["2001:db8:*::1"], "target": [], "excluded": []}}))
