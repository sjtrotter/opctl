import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from opctl.adapters.json_repository import JsonPolicyRepository
from opctl.command_schema import handle_show, handle_write, handle_config


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
