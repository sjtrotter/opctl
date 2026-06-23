import sys
import pytest
from unittest.mock import MagicMock, patch

from opctl import cli
from opctl.command_schema import COMMAND_SCHEMA


def _run_main(argv, handler):
    """Run cli.main() for `argv` with the matching command's handler replaced.

    Patches get_os_interface so no real OS backend is resolved, and swaps the
    schema handler so we control what the dispatched command does.
    """
    cmd_ref = argv[1]
    with patch.object(sys, "argv", argv), \
         patch("opctl.cli.get_os_interface", return_value=MagicMock()), \
         patch("opctl.cli.JsonPolicyRepository", return_value=MagicMock(load_state=lambda: {})), \
         patch.dict(COMMAND_SCHEMA[cmd_ref], {"handler": handler}):
        cli.main()


class TestCliSurfacesProviderErrors:
    """Issue #52: a lazily-resolved provider that is unavailable must surface a
    clean, actionable message — never an unhandled traceback."""

    def test_runtime_error_is_surfaced_cleanly(self, capsys):
        def _raise(repo, os_adapter, payload):
            raise RuntimeError("No firewall backend is available. Set --firewall-provider.")

        with pytest.raises(SystemExit) as exc:
            _run_main(["opctl", "execute"], _raise)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "No firewall backend is available" in out
        assert "Traceback" not in out

    def test_value_error_is_surfaced_cleanly(self, capsys):
        def _raise(repo, os_adapter, payload):
            raise ValueError("firewall provider 'ghost' not found. Available: ['iptables']")

        with pytest.raises(SystemExit) as exc:
            _run_main(["opctl", "execute"], _raise)
        assert exc.value.code == 1
        assert "not found" in capsys.readouterr().out
