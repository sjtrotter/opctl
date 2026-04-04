from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter, IFirewallAdapter
from opctl.domain.services.ip_parser import IPParser

class CommitPolicyUseCase:
    """Orchestrates the interface teardown, identity spoofing, and firewall commit."""
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter, fw_os: IFirewallAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os
        self.fw_os = fw_os

    def execute(self) -> None:
        staged_dict = self.repo.load_state()
        profile = OpProfile.from_dict(staged_dict)
        iface = profile.interface.name

        if not iface:
            raise ValueError("Cannot commit policy without a defined network interface.")

        self.net_os.set_link_state(iface, "down")

        if profile.identity.hostname:
            self.sys_os.set_hostname(profile.identity.hostname)
        
        # MAC is now strictly on the interface object
        if profile.interface.mac_address:
            self.net_os.set_mac_address(iface, profile.interface.mac_address)

        self.fw_os.flush_managed_rules()
        compiled_policy = profile.policy.compile(IPParser.parse)
        
        self.fw_os.apply_ipv4_blocks(compiled_policy["v4"]["blocked"], compiled_policy["v4"]["port_blocks"])
        self.fw_os.apply_ipv6_blocks(compiled_policy["v6"]["blocked"], compiled_policy["v6"]["port_blocks"])
        
        self.fw_os.apply_ipv4_allows(
            compiled_policy["v4"]["targets"] + compiled_policy["v4"]["trusted"],
            compiled_policy["v4"]["port_allows"]
        )
        self.fw_os.apply_ipv6_allows(
            compiled_policy["v6"]["targets"] + compiled_policy["v6"]["trusted"],
            compiled_policy["v6"]["port_allows"]
        )

        if profile.interface.is_static():
            self.net_os.configure_static(
                iface, profile.interface.ip_address, profile.interface.gateway, profile.interface.dns_servers
            )
        else:
            self.net_os.configure_dhcp(iface)

        self.net_os.set_link_state(iface, "up")