import json
import os
import tempfile
from unittest.mock import MagicMock, call
import pytest

from opctl.adapters.json_repository import JsonPolicyRepository
from opctl.use_cases.bulk_configure_uc import BulkConfigureUseCase
from opctl.use_cases.commit_policy_uc import CommitPolicyUseCase
from opctl.use_cases.list_interfaces_uc import ListInterfacesUseCase
from opctl.use_cases.remove_rule_uc import RemoveRuleUseCase
from opctl.use_cases.view_status_uc import ViewStatusUseCase
from opctl.use_cases.status_report_uc import StatusReportUseCase


def _tmp_repo(initial_state=None):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    if initial_state is not None:
        with open(path, "w") as f:
            json.dump(initial_state, f)
    else:
        os.unlink(path)
    return JsonPolicyRepository(path), path


def _cleanup(path):
    if os.path.exists(path):
        os.unlink(path)


class TestBulkConfigureUseCase:

    def test_stages_hostname(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({"system": {"hostname": "ops-box"}})
            state = repo.load_state()
            assert state["system"]["hostname"] == "ops-box"
        finally:
            _cleanup(path)

    def test_stages_interface_ip(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({
                "interface_name": "eth0",
                "interface_config": {"ip": ["10.0.0.1/24"], "mode": "static"}
            })
            state = repo.load_state()
            assert state["interfaces"]["eth0"]["ip_addresses"] == ["10.0.0.1/24"]
            assert state["interfaces"]["eth0"]["mode"] == "static"
        finally:
            _cleanup(path)

    def test_stages_interface_mac_random(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({
                "interface_name": "eth0",
                "interface_config": {"mac": "random"}
            })
            state = repo.load_state()
            assert state["interfaces"]["eth0"]["randomize_mac"] is True
        finally:
            _cleanup(path)

    def test_stages_interface_explicit_mac(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({
                "interface_name": "eth0",
                "interface_config": {"mac": "aa:bb:cc:dd:ee:ff"}
            })
            state = repo.load_state()
            assert state["interfaces"]["eth0"]["mac_address"] == "aa:bb:cc:dd:ee:ff"
            assert state["interfaces"]["eth0"]["randomize_mac"] is False
        finally:
            _cleanup(path)

    def test_stages_global_firewall_rules(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({"policy": {
                "target": ["192.168.1.0/24"],
                "trusted": ["10.0.0.0/8"],
                "excluded": ["10.0.5.0/24"],
            }})
            gp = repo.load_state()["global_policy"]
            assert "192.168.1.0/24" in gp["target"]
            assert "10.0.0.0/8" in gp["trusted"]
            assert "10.0.5.0/24" in gp["excluded"]
        finally:
            _cleanup(path)

    def test_stages_interface_firewall_rules(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({
                "interface_name": "eth0",
                "interface_config": {"excluded": ["10.0.0.0/8"], "target": "1.2.3.4"},
            })
            pol = repo.load_state()["interfaces"]["eth0"]["policy"]
            assert "10.0.0.0/8" in pol["excluded"]
            assert "1.2.3.4" in pol["target"]  # a bare string is accepted, not only a list
        finally:
            _cleanup(path)

    def test_stages_ntp_servers(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({"ntp": {"servers": ["0.pool.ntp.org"]}})
            state = repo.load_state()
            assert state["ntp"]["servers"] == ["0.pool.ntp.org"]
        finally:
            _cleanup(path)

    def test_preserves_existing_state(self):
        repo, path = _tmp_repo({"system": {"hostname": "original", "unmanaged_policy": "ignore"}})
        try:
            BulkConfigureUseCase(repo).execute({"system": {"hostname": "updated"}})
            state = repo.load_state()
            assert state["system"]["hostname"] == "updated"
            assert state["system"]["unmanaged_policy"] == "ignore"
        finally:
            _cleanup(path)

    def test_interface_without_link_flags_stays_enabled(self):
        # Regression for #16: staging interface config that omits enable/disable
        # must leave the interface at its enabled-by-default state.
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({
                "interface_name": "eth0",
                "interface_config": {"ip": ["10.0.0.5/24"], "mode": "static"}
            })
            state = repo.load_state()
            assert state["interfaces"]["eth0"]["enabled"] is True
        finally:
            _cleanup(path)


class TestCommitPolicyUseCase:

    def _make_adapters(self):
        sys_mock = MagicMock()
        net_mock = MagicMock()
        fw_mock = MagicMock()
        return sys_mock, net_mock, fw_mock

    def test_sets_hostname_when_staged(self):
        repo, path = _tmp_repo({"system": {"hostname": "tgt-box"}})
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            sys_m.set_hostname.assert_called_once_with("tgt-box")
        finally:
            _cleanup(path)

    def test_skips_hostname_when_not_staged(self):
        repo, path = _tmp_repo({})
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            sys_m.set_hostname.assert_not_called()
        finally:
            _cleanup(path)

    def test_flushes_firewall_rules(self):
        repo, path = _tmp_repo({})
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            fw_m.flush_managed_rules.assert_called_once()
        finally:
            _cleanup(path)

    def test_configures_static_interface(self):
        state = {
            "interfaces": {
                "eth0": {
                    "mode": "static",
                    "ip_addresses": ["10.0.0.5/24"],
                    "gateway": "10.0.0.1",
                    "dns_servers": ["8.8.8.8"],
                    "enabled": True
                }
            }
        }
        repo, path = _tmp_repo(state)
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            net_m.configure_static.assert_called_once_with("eth0", "10.0.0.5/24", "10.0.0.1", ["8.8.8.8"])
        finally:
            _cleanup(path)

    def test_configures_dhcp_interface(self):
        state = {
            "interfaces": {
                "eth0": {
                    "mode": "dhcp",
                    "ip_addresses": [],
                    "gateway": "",
                    "dns_servers": [],
                    "enabled": True
                }
            }
        }
        repo, path = _tmp_repo(state)
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            net_m.configure_dhcp.assert_called_once_with("eth0")
        finally:
            _cleanup(path)

    def test_disabled_interface_set_down_and_skipped(self):
        state = {
            "interfaces": {
                "eth0": {
                    "mode": "static",
                    "ip_addresses": ["10.0.0.1/24"],
                    "gateway": "",
                    "dns_servers": [],
                    "enabled": False
                }
            }
        }
        repo, path = _tmp_repo(state)
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            net_m.set_link_state.assert_called_once_with("eth0", "down")
            net_m.configure_static.assert_not_called()
        finally:
            _cleanup(path)

    def test_successful_commit_reports_all_steps_ok(self):
        repo, path = _tmp_repo({"system": {"hostname": "tgt-box"}})
        sys_m, net_m, fw_m = self._make_adapters()
        try:
            report = CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            assert report.success is True
            assert report.rolled_back is False
            assert report.steps and all(s.status == "ok" for s in report.steps)
        finally:
            _cleanup(path)

    def test_rolls_back_to_snapshot_on_failure(self):
        state = {
            "system": {"hostname": "tgt-box"},
            "interfaces": {"eth0": {
                "mode": "static", "ip_addresses": ["10.0.0.5/24"], "gateway": "",
                "dns_servers": [], "enabled": True, "mac_address": "aa:bb:cc:dd:ee:ff",
            }},
        }
        repo, path = _tmp_repo(state)
        sys_m, net_m, fw_m = self._make_adapters()
        sys_m.get_hostname.return_value = "old-host"
        net_m.set_mac_address.side_effect = RuntimeError("device busy")
        try:
            report = CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            assert report.success is False
            assert report.rolled_back is True
            assert any(s.status == "failed" for s in report.steps)
            # the pre-commit hostname snapshot is restored during rollback
            sys_m.set_hostname.assert_any_call("old-host")
        finally:
            _cleanup(path)

    def test_steps_after_failure_are_skipped(self):
        repo, path = _tmp_repo({"system": {"hostname": "tgt-box"}})
        sys_m, net_m, fw_m = self._make_adapters()
        fw_m.flush_managed_rules.side_effect = RuntimeError("no firewall backend")
        try:
            report = CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            assert report.success is False
            assert any(s.status == "failed" for s in report.steps)
            assert any(s.status == "skipped" for s in report.steps)
        finally:
            _cleanup(path)

    def test_invalid_firewall_rule_fails_and_rolls_back(self):
        # A bad staged rule must fail the commit (and roll back), not crash:
        # compile() runs inside the tracked step.
        state = {"system": {"hostname": "tgt"},
                 "global_policy": {"trusted": [], "target": ["not-an-ip"], "excluded": []}}
        repo, path = _tmp_repo(state)
        sys_m, net_m, fw_m = self._make_adapters()
        sys_m.get_hostname.return_value = "old"
        try:
            report = CommitPolicyUseCase(repo, sys_m, net_m, fw_m).execute()
            assert report.success is False
            assert report.rolled_back is True
            assert any(s.status == "failed" and "global policy" in s.name for s in report.steps)
        finally:
            _cleanup(path)


class TestRemoveRuleUseCase:

    def test_removes_rule_from_global_policy(self):
        # Regression for #19: the use case must target global_policy (not a
        # nonexistent profile.policy attribute) and actually remove the rule.
        state = {"global_policy": {"trusted": [], "target": ["10.0.0.0/24", "192.168.1.0/24"], "excluded": []}}
        repo, path = _tmp_repo(state)
        try:
            RemoveRuleUseCase(repo).execute("target", ["10.0.0.0/24"])
            result = repo.load_state()
            assert "10.0.0.0/24" not in result["global_policy"]["target"]
            assert "192.168.1.0/24" in result["global_policy"]["target"]
        finally:
            _cleanup(path)

    def test_removing_absent_rule_is_noop(self):
        state = {"global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []}}
        repo, path = _tmp_repo(state)
        try:
            RemoveRuleUseCase(repo).execute("target", ["172.16.0.0/24"])
            result = repo.load_state()
            assert "10.0.0.0/24" in result["global_policy"]["target"]
        finally:
            _cleanup(path)

    def test_removes_rule_from_interface_policy(self):
        state = {"interfaces": {"eth0": {"policy": {
            "trusted": [], "target": [], "excluded": ["10.0.0.0/8", "172.16.0.0/12"]}}}}
        repo, path = _tmp_repo(state)
        try:
            RemoveRuleUseCase(repo).execute("excluded", ["10.0.0.0/8"], interface="eth0")
            pol = repo.load_state()["interfaces"]["eth0"]["policy"]
            assert "10.0.0.0/8" not in pol["excluded"]
            assert "172.16.0.0/12" in pol["excluded"]
        finally:
            _cleanup(path)

    def test_remove_from_unstaged_interface_is_noop(self):
        repo, path = _tmp_repo({"global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []}})
        try:
            removed = RemoveRuleUseCase(repo).execute("excluded", ["1.2.3.4"], interface="eth99")
            assert removed == 0
            assert "10.0.0.0/24" in repo.load_state()["global_policy"]["target"]
        finally:
            _cleanup(path)

    def test_removes_multiple_and_returns_actual_count(self):
        state = {"global_policy": {"trusted": [],
                 "target": ["10.0.0.0/24", "10.1.0.0/24", "10.2.0.0/24"], "excluded": []}}
        repo, path = _tmp_repo(state)
        try:
            # two exist, one does not — only the two present should count
            removed = RemoveRuleUseCase(repo).execute("target", ["10.0.0.0/24", "10.1.0.0/24", "172.16.0.0/24"])
            assert removed == 2
            tgt = repo.load_state()["global_policy"]["target"]
            assert "10.2.0.0/24" in tgt
            assert "10.0.0.0/24" not in tgt and "10.1.0.0/24" not in tgt
        finally:
            _cleanup(path)

    def test_returns_zero_when_nothing_matched(self):
        repo, path = _tmp_repo({"global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []}})
        try:
            assert RemoveRuleUseCase(repo).execute("target", ["172.16.0.0/24"]) == 0
        finally:
            _cleanup(path)


class TestListInterfacesUseCase:

    def test_returns_interfaces_with_live_details(self):
        repo, path = _tmp_repo({})
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = ["eth0", "wlan0"]
        net_m.get_mac_address.side_effect = lambda i: f"aa:bb:cc:dd:ee:{i[-1]}"
        net_m.get_ip_address.side_effect = lambda i: "192.168.1.1"
        try:
            result = ListInterfacesUseCase(repo, net_m).execute()
            assert len(result["interfaces"]) == 2
            assert result["interfaces"][0]["name"] == "eth0"
        finally:
            _cleanup(path)

    def test_marks_staged_interfaces(self):
        state = {"interfaces": {"eth0": {"mode": "static", "ip_addresses": [], "gateway": "", "dns_servers": []}}}
        repo, path = _tmp_repo(state)
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = ["eth0", "wlan0"]
        net_m.get_mac_address.return_value = "aa:bb:cc:dd:ee:ff"
        net_m.get_ip_address.return_value = "Unassigned"
        try:
            result = ListInterfacesUseCase(repo, net_m).execute()
            by_name = {i["name"]: i for i in result["interfaces"]}
            assert by_name["eth0"]["is_staged"] is True
            assert by_name["wlan0"]["is_staged"] is False
        finally:
            _cleanup(path)


class TestViewStatusUseCase:

    def test_hostname_match_when_synced(self):
        repo, path = _tmp_repo({"system": {"hostname": "ops-box"}})
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ops-box"
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = []
        net_m.get_dns_servers.return_value = []
        try:
            data = ViewStatusUseCase(repo, sys_m, net_m).execute()
            assert data["System"]["Hostname"]["match"] is True
        finally:
            _cleanup(path)

    def test_hostname_diff_when_diverged(self):
        repo, path = _tmp_repo({"system": {"hostname": "new-name"}})
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "old-name"
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = []
        net_m.get_dns_servers.return_value = []
        try:
            data = ViewStatusUseCase(repo, sys_m, net_m).execute()
            assert data["System"]["Hostname"]["match"] is False
            assert data["System"]["Hostname"]["state"] == "changed"
        finally:
            _cleanup(path)

    def test_unstaged_hostname_is_unset(self):
        repo, path = _tmp_repo({})
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ubuntu"
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = []
        net_m.get_dns_servers.return_value = []
        try:
            data = ViewStatusUseCase(repo, sys_m, net_m).execute()
            assert data["System"]["Hostname"]["state"] == "unset"
        finally:
            _cleanup(path)

    def test_staged_only_firewall_is_not_synced(self):
        # Regression: firewall rules have no live equivalent and must report
        # 'staged', never a misleading 'synced'/SYNC.
        repo, path = _tmp_repo({"global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []}})
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ubuntu"
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = []
        net_m.get_dns_servers.return_value = []
        try:
            data = ViewStatusUseCase(repo, sys_m, net_m).execute()
            assert data["Global Policy"]["V4 Targets"]["state"] == "staged"
            assert data["Global Policy"]["V4 Trusted"]["state"] == "unset"
        finally:
            _cleanup(path)


class TestStatusReportUseCase:

    def _net(self, **overrides):
        net_m = MagicMock()
        net_m.get_available_interfaces.return_value = overrides.get("ifaces", [])
        net_m.get_dns_servers.return_value = []
        return net_m

    def test_empty_profile_reports_nothing_staged(self):
        repo, path = _tmp_repo({})
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ubuntu"
        try:
            out = "\n".join(StatusReportUseCase(repo, sys_m, self._net()).execute("root"))
            assert "No staged configuration" in out
        finally:
            _cleanup(path)

    def test_changes_are_bucketed_and_no_fake_sync(self):
        state = {
            "system": {"hostname": "recon-01"},
            "interfaces": {"eth0": {
                "mode": "static", "ip_addresses": ["10.10.0.5/24"],
                "gateway": "10.10.0.1", "dns_servers": [], "enabled": True,
            }},
        }
        repo, path = _tmp_repo(state)
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ubuntu"
        net_m = self._net(ifaces=["eth0"])
        net_m.get_mac_address.return_value = "aa:bb:cc:dd:ee:01"
        net_m.get_ip_address.return_value = "10.0.0.9"
        net_m.get_gateway.return_value = "10.0.0.1"
        net_m.is_dhcp_enabled.return_value = True
        try:
            out = "\n".join(StatusReportUseCase(repo, sys_m, net_m).execute("root"))
            assert "staged vs live" in out
            assert "CHANGES" in out
            assert "recon-01" in out and "->" in out
            # empty firewall zones must not appear as noise
            assert "v4 trusted" not in out
        finally:
            _cleanup(path)

    def test_staged_only_listed_separately(self):
        state = {
            "system": {"hostname": "", "unmanaged_policy": "isolate"},
            "global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []},
        }
        repo, path = _tmp_repo(state)
        sys_m = MagicMock()
        sys_m.get_hostname.return_value = "ubuntu"
        try:
            out = "\n".join(StatusReportUseCase(repo, sys_m, self._net()).execute("root"))
            assert "STAGED" in out
            assert "Isolate" in out
            assert "10.0.0.0/24" in out
            assert "CHANGES" not in out  # nothing comparable is staged
        finally:
            _cleanup(path)
