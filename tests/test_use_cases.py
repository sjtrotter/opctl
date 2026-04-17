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

    def test_stages_global_target(self):
        repo, path = _tmp_repo()
        try:
            BulkConfigureUseCase(repo).execute({"targets": "192.168.1.0/24"})
            state = repo.load_state()
            assert "192.168.1.0/24" in state["global_policy"]["target"]
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
        finally:
            _cleanup(path)
