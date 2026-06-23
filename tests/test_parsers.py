import unittest
import ipaddress
from opctl.domain.services.ip_parser import IPParser
from opctl.domain.exceptions.network import InvalidNetworkFormatError

class TestIPParser(unittest.TestCase):
    
    def test_standard_ipv4_cidr(self):
        """Test standard CIDR notation passes through cleanly."""
        result = IPParser.parse("192.168.0.0/24")
        self.assertEqual(len(result), 1)
        self.assertIn(ipaddress.IPv4Network("192.168.0.0/24"), result)

    def test_ipv4_dashed_octet_with_cidr(self):
        """Test dashed octet expands into multiple base networks."""
        result = IPParser.parse("192.168.0-1.0/24")
        self.assertEqual(len(result), 2)
        self.assertIn(ipaddress.IPv4Network("192.168.0.0/24"), result)
        self.assertIn(ipaddress.IPv4Network("192.168.1.0/24"), result)

    def test_ipv4_splat_with_dash(self):
        """Test complex splat and dash permutations."""
        # This means: 192.168.[0-255].[10, 11, 12]/32
        result = IPParser.parse("192.168.*.10-12")
        self.assertEqual(len(result), 256 * 3) # 768 unique networks
        self.assertIn(ipaddress.IPv4Network("192.168.5.11/32"), result)

    def test_ipv6_standard_cidr(self):
        """Test standard IPv6 CIDR parses correctly."""
        result = IPParser.parse("2001:db8::/32")
        self.assertEqual(len(result), 1)
        self.assertIn(ipaddress.IPv6Network("2001:db8::/32"), result)

    def test_ipv6_rejects_splat(self):
        """Ensure IPv6 throws a domain error if given a splat (memory safety)."""
        with self.assertRaises(InvalidNetworkFormatError):
            IPParser.parse("2001:db8::*/64")

    def test_invalid_dash_range(self):
        """Ensure inverted dashes are caught."""
        with self.assertRaises(InvalidNetworkFormatError):
            IPParser.parse("192.168.50-10.0/24")

    def test_rejects_full_splat_expansion_dos(self):
        """A splat across all octets would expand to 2^32 networks: reject, don't hang."""
        for s in ("*.*.*.*", "*.*.*.10", "10.*.*.*"):
            with self.assertRaises(InvalidNetworkFormatError):
                IPParser.parse(s)

    def test_rejects_oversized_dash_range_expansion(self):
        """A dash range whose product exceeds the cap is rejected before expansion."""
        with self.assertRaises(InvalidNetworkFormatError):
            IPParser.parse("0-255.0-255.0-255.10")

    def test_rejects_leading_and_trailing_dots(self):
        """Empty octets (leading/trailing/double dots) must not recurse or pass."""
        for s in (".10.0.0.1", "10.0.0.1.", "10..0.1", "10.0.0.1.5"):
            with self.assertRaises(InvalidNetworkFormatError):
                IPParser.parse(s)

    def test_rejects_deeply_nested_dots_without_recursion_error(self):
        """A pathological dotted string is a clean domain error, not a RecursionError."""
        with self.assertRaises(InvalidNetworkFormatError):
            IPParser.parse("1." * 2000)

    def test_single_splat_octet_still_expands(self):
        """The cap must not break the common, bounded single-splat case."""
        result = IPParser.parse("192.168.*.10")
        self.assertEqual(len(result), 256)

if __name__ == '__main__':
    unittest.main()