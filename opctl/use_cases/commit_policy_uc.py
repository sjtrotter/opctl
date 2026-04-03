from opctl.domain.models import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter, IFirewallAdapter
from opctl.domain.services import IPParser

class CommitPolicyUseCase:
    """
    The Master Sequence. Safely orchestrates the interface teardown, 
    identity spoofing, and firewall rule compilation.
    """
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter, fw_os: IFirewallAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os
        self.fw_os = fw_os

    def execute(self) -> None:
        # 1. Load Staged Configuration
        staged_dict = self.repo.load_state()
        profile = OpProfile(staged_dict)
        iface = profile.interface.name

        # Validate we have an interface to operate on
        if not iface:
            raise ValueError("Cannot commit policy without a defined network interface.")

        # --- THE RADIO SILENCE PROVISIONING FLOW ---
        
        # Step 1: Drop the Link (Prevent packet leaks during identity change)
        self.net_os.set_link_state(iface, "down")

        # Step 2: Spoof Identity
        if profile.identity.hostname:
            self.sys_os.set_hostname(profile.identity.hostname)
        if profile.identity.mac_address:
            self.net_os.set_mac_address(iface, profile.identity.mac_address)

        # Step 3: Lock the Doors (Firewall Compilation & Execution)
        self.fw_os.flush_managed_rules()
        compiled_policy = profile.policy.compile(IPParser.parse)
        
        # Apply Drops FIRST (Ports overrides first inside the adapter, then CIDR blocks)
        self.fw_os.apply_ipv4_blocks(
            compiled_policy["v4"]["blocked"], 
            compiled_policy["v4"]["port_blocks"]
        )
        self.fw_os.apply_ipv6_blocks(
            compiled_policy["v6"]["blocked"], 
            compiled_policy["v6"]["port_blocks"]
        )
        
        # Apply Allows SECOND (Port overrides first inside the adapter, then CIDR blocks)
        self.fw_os.apply_ipv4_allows(
            compiled_policy["v4"]["targets"] + compiled_policy["v4"]["trusted"],
            compiled_policy["v4"]["port_allows"]
        )
        self.fw_os.apply_ipv6_allows(
            compiled_policy["v6"]["targets"] + compiled_policy["v6"]["trusted"],
            compiled_policy["v6"]["port_allows"]
        )

        # Step 4: Configure Routing (Static vs DHCP)
        if profile.interface.is_static():
            self.net_os.configure_static(
                iface, 
                profile.interface.ip_address, 
                profile.interface.gateway, 
                profile.interface.dns_servers
            )
        else:
            self.net_os.configure_dhcp(iface)

        # Step 5: Go Hot
        self.net_os.set_link_state(iface, "up")