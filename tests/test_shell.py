import json
import os
import tempfile
from unittest.mock import MagicMock
import pytest

from opctl.adapters.json_repository import JsonPolicyRepository
from opctl.shell import OpctlShell


def _make_shell(initial_state=None):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    if initial_state is not None:
        with open(path, "w") as f:
            json.dump(initial_state, f)
    else:
        os.unlink(path)
    repo = JsonPolicyRepository(path)
    adapter = MagicMock()
    adapter.get_available_interfaces.return_value = []
    adapter.get_hostname.return_value = "testhost"
    adapter.get_dns_servers.return_value = []
    shell = OpctlShell(repo, adapter)
    return shell, path


def _cleanup(path):
    if os.path.exists(path):
        os.unlink(path)


class TestOpctlShellModes:

    def test_initial_mode_is_root(self):
        shell, path = _make_shell()
        try:
            assert shell.current_mode == "root"
            assert shell.prompt == "opctl# "
        finally:
            _cleanup(path)

    def test_configure_changes_mode_and_prompt(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            assert shell.current_mode == "configure"
            assert "config" in shell.prompt
        finally:
            _cleanup(path)

    def test_system_changes_mode(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_system("")
            assert shell.current_mode == "system"
            assert "system" in shell.prompt
        finally:
            _cleanup(path)

    def test_interface_sets_interface_context(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_interface("eth0")
            assert shell.current_mode == "interface"
            assert shell.current_interface == "eth0"
            assert "eth0" in shell.prompt
        finally:
            _cleanup(path)

    def test_interface_without_name_stays_in_configure(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_interface("")
            assert shell.current_mode == "configure"
        finally:
            _cleanup(path)

    def test_exit_from_system_returns_to_configure(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_system("")
            shell.do_exit("")
            assert shell.current_mode == "configure"
        finally:
            _cleanup(path)

    def test_exit_from_configure_returns_to_root(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_exit("")
            assert shell.current_mode == "root"
            assert shell.prompt == "opctl# "
        finally:
            _cleanup(path)

    def test_exit_from_interface_returns_to_configure(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            shell.do_interface("eth0")
            shell.do_exit("")
            assert shell.current_mode == "configure"
            assert shell.current_interface is None
        finally:
            _cleanup(path)

    def test_alias_configure_conf(self):
        shell, path = _make_shell()
        try:
            resolved = shell.precmd("conf")
            assert resolved.startswith("configure")
        finally:
            _cleanup(path)

    def test_alias_system_sys(self):
        shell, path = _make_shell()
        try:
            shell.do_configure("")
            resolved = shell.precmd("sys")
            assert resolved.startswith("system")
        finally:
            _cleanup(path)

    def test_command_invalid_in_wrong_mode_prints_error(self, capsys):
        shell, path = _make_shell()
        try:
            # 'hostname' is only valid in 'system' mode, not 'root'
            shell.do_hostname("newname")
            captured = capsys.readouterr()
            assert "not valid" in captured.out
        finally:
            _cleanup(path)

    def test_precmd_resolves_alias(self):
        shell, path = _make_shell()
        try:
            result = shell.precmd("conf")
            assert result.startswith("configure")
        finally:
            _cleanup(path)

    def test_precmd_prefix_expansion(self):
        shell, path = _make_shell()
        try:
            result = shell.precmd("exe")
            assert result.startswith("execute")
        finally:
            _cleanup(path)
