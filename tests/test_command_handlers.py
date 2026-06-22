import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from opctl.adapters.json_repository import JsonPolicyRepository
from opctl.command_schema import handle_show, handle_write, handle_config, handle_remove, handle_import


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


class TestHandleWrite:

    def test_honors_value_target_path(self):
        # Regression for #18: the positional is carried under payload['value'];
        # write must export to it, not always to the default session.json.
        repo, path = _tmp_repo({"system": {"hostname": "ops-box"}})
        out_path = tempfile.mktemp(suffix=".json")
        try:
            handle_write(repo, MagicMock(), {"value": out_path})
            assert os.path.exists(out_path)
            with open(out_path) as f:
                data = json.load(f)
            assert data["system"]["hostname"] == "ops-box"
        finally:
            _cleanup(path)
            _cleanup(out_path)


class TestHandleShow:

    def test_value_interfaces_lists_os_interfaces(self, capsys):
        # Regression for #18: `show interfaces` must reach the interface listing
        # branch (previously unreachable because the handler read 'target').
        repo, path = _tmp_repo({})
        net = MagicMock()
        net.get_available_interfaces.return_value = ["eth0"]
        net.get_mac_address.return_value = "aa:bb:cc:dd:ee:ff"
        net.get_ip_address.return_value = "10.0.0.5"
        try:
            handle_show(repo, net, {"value": "interfaces"})
            out = capsys.readouterr().out
            assert "Available OS Network Interfaces" in out
            assert "eth0" in out
        finally:
            _cleanup(path)

    def test_edits_threads_mode_and_interface_context(self):
        # Regression for #18: shell mode / interface context must be passed to
        # the status report so per-mode filtering works.
        repo, path = _tmp_repo({})
        try:
            with patch("opctl.command_schema.StatusReportUseCase") as SR:
                SR.return_value.execute.return_value = []
                handle_show(repo, MagicMock(),
                            {"value": "edits", "_mode": "interface", "_interface": "eth0"})
                SR.return_value.execute.assert_called_once_with("interface", "eth0")
        finally:
            _cleanup(path)

    def test_defaults_to_edits_when_no_value(self):
        repo, path = _tmp_repo({})
        try:
            with patch("opctl.command_schema.StatusReportUseCase") as SR:
                SR.return_value.execute.return_value = []
                handle_show(repo, MagicMock(), {})
                SR.return_value.execute.assert_called_once_with("root", None)
        finally:
            _cleanup(path)


class TestHandleConfig:

    def test_confirmation_does_not_leak_internal_keys(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_config(repo, MagicMock(),
                          {"_mode": "policy", "_interface": None, "policy": {"target": ["10.0.0.0/24"]}})
            out = capsys.readouterr().out
            assert "_mode" not in out
            assert "policy" in out
        finally:
            _cleanup(path)

    def test_confirmation_names_the_interface(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_config(repo, MagicMock(),
                          {"_mode": "interface", "_interface": "eth0",
                           "interface_name": "eth0", "interface_config": {"trusted": ["192.168.0.0/16"]}})
            out = capsys.readouterr().out
            assert "eth0" in out
        finally:
            _cleanup(path)


class TestHandleRemove:

    def test_removes_global_rule(self):
        repo, path = _tmp_repo({"global_policy": {
            "trusted": [], "target": ["10.0.0.0/24", "10.1.0.0/24"], "excluded": []}})
        try:
            handle_remove(repo, MagicMock(),
                          {"_mode": "policy", "policy": {"no": ["target", "10.0.0.0/24"]}})
            gp = repo.load_state()["global_policy"]
            assert "10.0.0.0/24" not in gp["target"]
            assert "10.1.0.0/24" in gp["target"]
        finally:
            _cleanup(path)

    def test_removes_interface_rule(self):
        state = {"interfaces": {"eth0": {"policy": {
            "trusted": [], "target": [], "excluded": ["10.0.0.0/8"]}}}}
        repo, path = _tmp_repo(state)
        try:
            handle_remove(repo, MagicMock(),
                          {"_mode": "interface", "_interface": "eth0", "interface_name": "eth0",
                           "interface_config": {"no": ["excluded", "10.0.0.0/8"]}})
            pol = repo.load_state()["interfaces"]["eth0"]["policy"]
            assert "10.0.0.0/8" not in pol["excluded"]
        finally:
            _cleanup(path)

    def test_unknown_zone_is_rejected(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_remove(repo, MagicMock(), {"policy": {"no": ["bogus", "10.0.0.0/24"]}})
            assert "Unknown zone" in capsys.readouterr().out
        finally:
            _cleanup(path)

    def test_missing_network_prints_usage(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_remove(repo, MagicMock(), {"policy": {"no": ["target"]}})
            assert "Usage" in capsys.readouterr().out
        finally:
            _cleanup(path)

    def test_reports_actual_removed_count(self, capsys):
        repo, path = _tmp_repo({"global_policy": {"trusted": [],
                                "target": ["10.0.0.0/24", "10.1.0.0/24"], "excluded": []}})
        try:
            handle_remove(repo, MagicMock(), {"policy": {"no": ["target", "10.0.0.0/24", "10.1.0.0/24"]}})
            assert "Removed 2 rule(s)" in capsys.readouterr().out
        finally:
            _cleanup(path)

    def test_no_match_reports_nothing_removed_and_preserves_state(self, capsys):
        repo, path = _tmp_repo({"global_policy": {"trusted": [], "target": ["10.0.0.0/24"], "excluded": []}})
        try:
            handle_remove(repo, MagicMock(), {"policy": {"no": ["target", "172.16.0.0/24"]}})
            out = capsys.readouterr().out
            assert "No matching" in out
            assert "Removed" not in out
            assert "10.0.0.0/24" in repo.load_state()["global_policy"]["target"]
        finally:
            _cleanup(path)

    def test_unstaged_interface_does_not_claim_removal(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_remove(repo, MagicMock(),
                          {"interface_name": "eth9", "interface_config": {"no": ["excluded", "10.0.0.0/8"]}})
            out = capsys.readouterr().out
            assert "Removed" not in out
            assert "No matching" in out
        finally:
            _cleanup(path)


class TestHandleImport:

    def test_imports_and_reports(self, capsys):
        pb_fd, pb_path = tempfile.mkstemp(suffix=".json")
        os.close(pb_fd)
        with open(pb_path, "w") as f:
            json.dump({"system": {"hostname": "from-playbook"}}, f)
        repo, path = _tmp_repo({})
        try:
            handle_import(repo, MagicMock(), {"value": pb_path})
            assert "Imported playbook" in capsys.readouterr().out
            assert repo.load_state()["system"]["hostname"] == "from-playbook"
        finally:
            _cleanup(path)
            _cleanup(pb_path)

    def test_missing_path_prints_usage(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_import(repo, MagicMock(), {})
            assert "Usage" in capsys.readouterr().out
        finally:
            _cleanup(path)

    def test_missing_file_prints_error_not_raise(self, capsys):
        repo, path = _tmp_repo({})
        try:
            handle_import(repo, MagicMock(), {"value": "/no/such/file.json"})
            assert "Import failed" in capsys.readouterr().out
        finally:
            _cleanup(path)

    def test_malformed_structure_prints_error_not_raise(self, capsys):
        # A wrong-typed substructure must surface as a message, not crash the shell/CLI.
        bad_fd, bad_path = tempfile.mkstemp(suffix=".json")
        os.close(bad_fd)
        with open(bad_path, "w") as f:
            json.dump({"interfaces": "x"}, f)
        repo, path = _tmp_repo({})
        try:
            handle_import(repo, MagicMock(), {"value": bad_path})  # must NOT raise
            assert "Import failed" in capsys.readouterr().out
        finally:
            _cleanup(path)
            _cleanup(bad_path)
