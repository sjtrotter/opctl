import pytest
from opctl.cli_parser import build_parser


class TestCliParser:

    def setup_method(self):
        self.parser = build_parser()

    def test_execute_parses(self):
        args = self.parser.parse_args(["execute"])
        assert args.command == "execute"

    def test_show_defaults_to_edits(self):
        args = self.parser.parse_args(["show"])
        assert args.command == "show"
        assert args.target == "edits"

    def test_show_interfaces(self):
        args = self.parser.parse_args(["show", "interfaces"])
        assert args.target == "interfaces"

    def test_show_edits_explicit(self):
        args = self.parser.parse_args(["show", "edits"])
        assert args.target == "edits"

    def test_write_defaults(self):
        args = self.parser.parse_args(["write"])
        assert args.command == "write"

    def test_system_hostname_flag(self):
        args = self.parser.parse_args(["system", "--hostname", "ops-box"])
        assert args.command == "system"
        assert args.hostname == "ops-box"

    def test_system_hostname_short_flag(self):
        args = self.parser.parse_args(["system", "-n", "ops-box"])
        assert args.hostname == "ops-box"

    def test_system_unmanaged_flag(self):
        args = self.parser.parse_args(["system", "--unmanaged", "isolate"])
        assert args.unmanaged == "isolate"

    def test_system_dns_single(self):
        args = self.parser.parse_args(["system", "--dns", "8.8.8.8"])
        assert args.dns == ["8.8.8.8"]

    def test_system_dns_multiple(self):
        args = self.parser.parse_args(["system", "--dns", "8.8.8.8", "1.1.1.1"])
        assert args.dns == ["8.8.8.8", "1.1.1.1"]

    def test_interface_requires_target(self):
        args = self.parser.parse_args(["interface", "eth0", "--ip", "10.0.0.1/24"])
        assert args.command == "interface"
        assert args.iface_target == "eth0"
        assert args.ip == ["10.0.0.1/24"]

    def test_interface_mac_flag(self):
        args = self.parser.parse_args(["interface", "eth0", "--mac", "aa:bb:cc:dd:ee:ff"])
        assert args.mac == "aa:bb:cc:dd:ee:ff"

    def test_interface_mode_flag(self):
        args = self.parser.parse_args(["interface", "eth0", "--mode", "dhcp"])
        assert args.mode == "dhcp"

    def test_interface_enable_flag(self):
        args = self.parser.parse_args(["interface", "eth0", "--enable"])
        assert args.enable is True

    def test_interface_disable_flag(self):
        args = self.parser.parse_args(["interface", "eth0", "--disable"])
        assert args.disable is True

    def test_system_alias_sys(self):
        args = self.parser.parse_args(["sys", "--hostname", "x"])
        assert args.hostname == "x"

    def test_interface_alias_int(self):
        args = self.parser.parse_args(["int", "eth0", "--mac", "random"])
        assert args.iface_target == "eth0"
        assert args.mac == "random"

    def test_unknown_command_raises_system_exit(self):
        with pytest.raises(SystemExit) as exc_info:
            self.parser.parse_args(["notacommand"])
        assert exc_info.value.code == 2
