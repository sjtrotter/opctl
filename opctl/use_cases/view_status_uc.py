from opctl.domain.models import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter
from opctl.domain.services import IPParser

class ViewStatusUseCase:
    """Orchestrates comparing the staged session state against the live OS state."""
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os

    def execute(self) -> dict:
        # 1. Load Staged Configuration
        staged_dict = self.repo.load_state()
        profile = OpProfile(staged_dict)
        
        # 2. Query Live OS State
        live_hostname = self.sys_os.get_hostname()
        iface = profile.interface.name
        
        # Only query network details if an interface is actively assigned
        live_mac = self.net_os.get_mac_address(iface) if iface else "No Interface Selected"
        live_ip = self.net_os.get_ip_address(iface) if iface else "No Interface Selected"

        # 3. Build the Diff Report for the CLI Adapter to format
        report = {
            "identity": {
                "hostname": {
                    "staged": profile.identity.hostname,
                    "live": live_hostname,
                    "match": profile.identity.hostname == live_hostname
                },
                "mac_address": {
                    "staged": profile.identity.mac_address,
                    "live": live_mac,
                    "match": profile.identity.mac_address == live_mac
                }
            },
            "interface": {
                "name": iface,
                "live_ip": live_ip
            },
            # Trigger the math compiler to preview firewall lines
            "policy_preview": profile.policy.compile(IPParser.parse) 
        }
        
        return report