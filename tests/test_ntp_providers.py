from unittest.mock import MagicMock, patch, mock_open
import pytest

from opctl.infrastructure.linux.providers.ntp.timesyncd import TimesyncdProvider
from opctl.infrastructure.linux.providers.ntp.chrony import ChronyProvider
from opctl.infrastructure.windows.providers.ntp.w32tm import W32tmProvider
from opctl.domain.services.validators import validate_ntp_server

_TS = "opctl.infrastructure.linux.providers.ntp.timesyncd"
_CH = "opctl.infrastructure.linux.providers.ntp.chrony"


def _linux(cls):
    p = cls.__new__(cls)
    p._run = MagicMock(return_value="")
    p._atomic_write = MagicMock()
    return p


def _w32(cls):
    p = cls.__new__(cls)
    p._run_cmd = MagicMock(return_value="")
    return p


class TestTimesyncdProvider:

    def test_set_servers_writes_reset_dropin_and_enables(self):
        p = _linux(TimesyncdProvider)
        with patch(_TS + ".os.makedirs"):
            p.set_servers(["0.pool.ntp.org", "10.0.0.2"], True)
        path, content = p._atomic_write.call_args[0][:2]
        assert path.endswith("90-opctl.conf")
        assert "NTP=\n" in content                       # the mandatory list reset
        assert "NTP=0.pool.ntp.org 10.0.0.2" in content
        cmds = [c.args[0] for c in p._run.call_args_list]
        assert ["timedatectl", "set-ntp", "true"] in cmds
        assert ["systemctl", "restart", "systemd-timesyncd"] in cmds

    def test_disabled_sets_ntp_false_without_restart(self):
        p = _linux(TimesyncdProvider)
        with patch(_TS + ".os.makedirs"):
            p.set_servers([], False)
        cmds = [c.args[0] for c in p._run.call_args_list]
        assert ["timedatectl", "set-ntp", "false"] in cmds
        assert not any("restart" in c for c in cmds)

    def test_rejects_bad_server(self):
        p = _linux(TimesyncdProvider)
        with pytest.raises(ValueError):
            p.set_servers(["bad host!"], True)

    def test_get_servers_parses_timedatectl(self):
        p = _linux(TimesyncdProvider)
        p._run.return_value = "0.pool.ntp.org 1.pool.ntp.org"
        assert p.get_servers() == ["0.pool.ntp.org", "1.pool.ntp.org"]

    def test_is_available_false_when_chrony_installed(self):
        with patch(_TS + ".shutil.which", side_effect=lambda b: "/usr/bin/" + b):
            assert TimesyncdProvider.is_available() is False

    def test_is_available_true_without_chrony(self):
        with patch(_TS + ".shutil.which",
                   side_effect=lambda b: "/usr/bin/timedatectl" if b == "timedatectl" else None):
            assert TimesyncdProvider.is_available() is True

    def test_is_available_covers_chronyc_without_chronyd_dead_zone(self):
        # chronyc present but chronyd absent -> chrony unresolvable -> timesyncd covers it
        def which(b):
            return None if b == "chronyd" else "/usr/bin/" + b
        with patch(_TS + ".shutil.which", side_effect=which):
            assert TimesyncdProvider.is_available() is True


class TestValidateNtpServer:

    def test_accepts_host_and_ip(self):
        assert validate_ntp_server("0.pool.ntp.org") == "0.pool.ntp.org"
        assert validate_ntp_server("10.0.0.2") == "10.0.0.2"

    def test_rejects_trailing_newline(self):
        # $ matches before a trailing \n; the validator must use \Z and reject it.
        with pytest.raises(ValueError):
            validate_ntp_server("10.0.0.2\n")
        with pytest.raises(ValueError):
            validate_ntp_server("host\n")

    def test_rejects_cidr(self):
        with pytest.raises(ValueError):
            validate_ntp_server("10.0.0.0/24")

    def test_rejects_shell_metacharacters(self):
        for bad in ['a" & calc', "a;b", "a b", "a|b", "$(x)"]:
            with pytest.raises(ValueError):
                validate_ntp_server(bad)


class TestChronyProvider:

    def test_set_servers_hot_reload_when_already_wired(self):
        p = _linux(ChronyProvider)
        p._ensure_sourcedir = MagicMock(return_value=False)
        with patch(_CH + ".os.makedirs"):
            p.set_servers(["10.0.0.2"], True)
        _, content = p._atomic_write.call_args[0][:2]
        assert "server 10.0.0.2 iburst" in content
        cmds = [c.args[0] for c in p._run.call_args_list]
        assert ["timedatectl", "set-ntp", "true"] in cmds
        assert ["chronyc", "reload", "sources"] in cmds

    def test_set_servers_restart_when_just_wired(self):
        p = _linux(ChronyProvider)
        p._ensure_sourcedir = MagicMock(return_value=True)
        with patch(_CH + ".os.makedirs"):
            p.set_servers(["10.0.0.2"], True)
        cmds = [c.args[0] for c in p._run.call_args_list]
        assert ["systemctl", "restart", "chronyd"] in cmds

    def test_disabled_only_toggles_set_ntp(self):
        p = _linux(ChronyProvider)
        p._ensure_sourcedir = MagicMock(return_value=False)
        with patch(_CH + ".os.makedirs"):
            p.set_servers([], False)
        cmds = [c.args[0] for c in p._run.call_args_list]
        assert ["timedatectl", "set-ntp", "false"] in cmds
        assert not any("reload" in c or "restart" in c for c in cmds)

    def test_ensure_sourcedir_idempotent_when_present(self):
        p = _linux(ChronyProvider)
        with patch("builtins.open", mock_open(read_data="sourcedir /etc/chrony/sources.d\n")):
            assert p._ensure_sourcedir() is False

    def test_ensure_sourcedir_appends_when_absent(self):
        p = _linux(ChronyProvider)
        m = mock_open(read_data="server pool.example\n")
        with patch("builtins.open", m):
            assert p._ensure_sourcedir() is True
        written = "".join(c.args[0] for c in m().write.call_args_list)
        assert "sourcedir /etc/chrony/sources.d" in written

    def test_rejects_bad_server(self):
        p = _linux(ChronyProvider)
        with pytest.raises(ValueError):
            p.set_servers(["not a host"], True)


class TestW32tmProvider:

    def test_set_servers_enabled_builds_manualpeerlist(self):
        p = _w32(W32tmProvider)
        p.set_servers(["time.windows.com", "10.0.0.2"], True)
        cmds = [c.args[0] for c in p._run_cmd.call_args_list]
        cfg = next(c for c in cmds if "/config" in c)
        assert "/manualpeerlist:" in cfg
        assert "time.windows.com,0x8" in cfg and "10.0.0.2,0x8" in cfg
        assert "/syncfromflags:manual" in cfg
        assert any("/resync" in c for c in cmds)

    def test_disabled_sets_syncfromflags_no(self):
        p = _w32(W32tmProvider)
        p.set_servers([], False)
        assert "/syncfromflags:NO" in p._run_cmd.call_args[0][0]

    def test_rejects_injection_server(self):
        p = _w32(W32tmProvider)
        with pytest.raises(ValueError):
            p.set_servers(['evil" & calc'], True)

    def test_get_servers_parses_registry(self):
        p = _w32(W32tmProvider)
        p._run_cmd.return_value = "    NtpServer    REG_SZ    time.windows.com,0x9 10.0.0.2,0x8"
        assert p.get_servers() == ["time.windows.com", "10.0.0.2"]

    def test_provider_name(self):
        assert W32tmProvider.provider_name() == "w32tm"
