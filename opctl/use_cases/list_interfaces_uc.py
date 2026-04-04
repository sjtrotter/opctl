from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, INetworkAdapter

class ListInterfacesUseCase:
    """Orchestrates querying the OS for hardware and diffing it against the staged session."""
    
    def __init__(self, repo: IPolicyRepository, net_os: INetworkAdapter):
        self.repo = repo
        self.net_os = net_os

    def execute(self) -> dict:
        # Load the staged state via factory
        staged_dict = self.repo.load_state()
        profile = OpProfile.from_dict(staged_dict)
        staged_iface = profile.interface.name

        interfaces = self.net_os.get_available_interfaces()
        
        result = []
        for iface in interfaces:
            # Query the live hardware details
            live_mac = self.net_os.get_mac_address(iface)
            live_ip = self.net_os.get_ip_address(iface)
            
            result.append({
                "name": iface,
                "mac": live_mac,
                "ip": live_ip,
                "is_staged": (iface == staged_iface)
            })
            
        return {
            "interfaces": result, 
            "staged_target": staged_iface
        }