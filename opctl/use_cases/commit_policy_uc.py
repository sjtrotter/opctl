from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter, IFirewallAdapter
from opctl.domain.services.ip_parser import IPParser

class CommitPolicyUseCase:
    """Orchestrates the interface teardown, identity spoofing, and granular firewall commit."""
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter, fw_os: IFirewallAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os
        self.fw_os = fw_os

    def execute(self) -> None:
        staged_dict = self.repo.load_state()
        profile = OpProfile.from_dict(staged_dict)

        # 1. Global System Identity
        if profile.system.hostname:
            self.sys_os.set_hostname(profile.system.hostname)

        # 2. Reset Firewall State
        self.fw_os.flush_managed_rules()

        # 3. Apply Global Firewall Policy
        global_pol = profile.global_policy.compile(IPParser.parse)
        self.fw_os.apply_ipv4_blocks(global_pol["v4"]["blocked"], global_pol["v4"]["port_blocks"])
        self.fw_os.apply_ipv6_blocks(global_pol["v6"]["blocked"], global_pol["v6"]["port_blocks"])
        self.fw_os.apply_ipv4_allows(global_pol["v4"]["targets"] + global_pol["v4"]["trusted"], global_pol["v4"]["port_allows"])
        self.fw_os.apply_ipv6_allows(global_pol["v6"]["targets"] + global_pol["v6"]["trusted"], global_pol["v6"]["port_allows"])

        # 4. Interface Configuration Loop
        for iname, iface in profile.interfaces.items():
            
            # LINK STATE CHECK: If administratively disabled, turn it off and skip config!
            if not iface.enabled:
                self.net_os.set_link_state(iname, "down")
                continue

            self.net_os.set_link_state(iname, "down")

            if iface.mac_address:
                self.net_os.set_mac_address(iname, iface.mac_address)

            # Apply Local Firewall Policy bound ONLY to this specific interface
            local_pol = iface.policy.compile(IPParser.parse)
            self.fw_os.apply_ipv4_blocks(local_pol["v4"]["blocked"], local_pol["v4"]["port_blocks"], interface=iname)
            self.fw_os.apply_ipv6_blocks(local_pol["v6"]["blocked"], local_pol["v6"]["port_blocks"], interface=iname)
            self.fw_os.apply_ipv4_allows(local_pol["v4"]["targets"] + local_pol["v4"]["trusted"], local_pol["v4"]["port_allows"], interface=iname)
            self.fw_os.apply_ipv6_allows(local_pol["v6"]["targets"] + local_pol["v6"]["trusted"], local_pol["v6"]["port_allows"], interface=iname)

            if iface.is_static():
                primary_ip = iface.ip_addresses[0] if iface.ip_addresses else ""
                self.net_os.configure_static(
                    iname, primary_ip, iface.gateway, iface.dns_servers
                )
            else:
                self.net_os.configure_dhcp(iname)

            self.net_os.set_link_state(iname, "up")