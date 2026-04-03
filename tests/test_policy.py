import unittest
from opctl.domain.models.policy import OpPolicy
from opctl.domain.services.ip_parser import IPParser

class TestOpPolicy(unittest.TestCase):

    def setUp(self):
        """Runs before every test to give us a fresh policy engine."""
        self.policy = OpPolicy()

    def test_compile_no_exclusions(self):
        """Test that adjacent networks collapse cleanly."""
        self.policy.add_rule("target", "192.168.0.0/24")
        self.policy.add_rule("target", "192.168.1.0/24")
        
        result = self.policy.compile(IPParser.parse)
        
        # They should collapse into a single /23
        self.assertEqual(len(result["v4"]["targets"]), 1)
        self.assertEqual(result["v4"]["targets"][0], "192.168.0.0/23")

    def test_compile_with_exclusions(self):
        """Test the Safety Valve: Subnet shattering around an exclusion."""
        self.policy.add_rule("target", "192.168.0.0/24")
        # Exclude the gateway
        self.policy.add_rule("excluded", "192.168.0.1")
        
        result = self.policy.compile(IPParser.parse)
        targets = result["v4"]["targets"]
        blocked = result["v4"]["blocked"]
        
        # The block rule should be explicitly returned
        self.assertIn("192.168.0.1/32", blocked)
        
        # The target /24 should be shattered into smaller blocks to bypass .1
        self.assertNotIn("192.168.0.0/24", targets)
        self.assertIn("192.168.0.0/32", targets) # The network ID is kept
        self.assertIn("192.168.0.2/31", targets) # .2 and .3
        self.assertIn("192.168.0.128/25", targets) # The top half of the subnet

    def test_v4_and_v6_separation(self):
        """Ensure dual-stack rules compile into the correct protocol buckets."""
        self.policy.add_rule("trusted", "10.0.0.0/8")
        self.policy.add_rule("trusted", "fe80::/10")
        
        result = self.policy.compile(IPParser.parse)
        
        self.assertIn("10.0.0.0/8", result["v4"]["trusted"])
        self.assertIn("fe80::/10", result["v6"]["trusted"])
        self.assertEqual(len(result["v6"]["targets"]), 0)

    def test_exclusion_larger_than_target(self):
        """Test if an operator accidentally excludes a massive block over a small target."""
        self.policy.add_rule("target", "192.168.1.50/32")
        self.policy.add_rule("excluded", "192.168.1.0/24") # Wipes out the whole /24
        
        result = self.policy.compile(IPParser.parse)
        
        # The target should be completely erased by the math
        self.assertEqual(len(result["v4"]["targets"]), 0)
        self.assertIn("192.168.1.0/24", result["v4"]["blocked"])

if __name__ == '__main__':
    unittest.main()