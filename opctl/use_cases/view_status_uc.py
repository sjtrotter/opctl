from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter
from opctl.domain.services.ip_parser import IPParser

class ViewStatusUseCase:
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os

    def execute(self) -> dict:
        staged_dict = self.repo.load_state()
        profile = OpProfile.from_dict(staged_dict)
        
        iface = profile.interface.name
        live_hostname = self.sys_os.get_hostname()
        
        live_mac, live_ip, live_gw, live_dns = "N/A", "Unassigned", "None", []
        os_is_dhcp = False

        if iface:
            live_mac = self.net_os.get_mac_address(iface)
            live_ip = self.net_os.get_ip_address(iface)
            live_gw = self.net_os.get_gateway(iface)
            live_dns = self.net_os.get_dns_servers(iface)
            os_is_dhcp = self.net_os.is_dhcp_enabled(iface)

        intent_is_dhcp = profile.interface.mode.lower() == "dhcp"
        mode_match = (intent_is_dhcp == os_is_dhcp)

        def format_live(val: str, is_dhcp_context: bool) -> str:
            if intent_is_dhcp and is_dhcp_context and os_is_dhcp:
                return f"DHCP (# {val})"
            return val

        return {
            "identity": {
                "hostname": {
                    "staged": profile.identity.hostname,
                    "live": live_hostname,
                    "match": profile.identity.hostname == live_hostname if profile.identity.hostname else False
                }
            },
            "interface": {
                "name": iface or "None",
                "mode": {
                    "staged": profile.interface.mode, 
                    "live": "dhcp" if os_is_dhcp else "static", 
                    "match": mode_match
                },
                "mac_address": {
                    "staged": profile.interface.mac_address or "Auto", 
                    "live": live_mac, 
                    "match": profile.interface.mac_address.lower() == live_mac.lower() if profile.interface.mac_address else False
                },
                "ip_address": {
                    "staged": profile.interface.ip_address or "DHCP", 
                    "live": format_live(live_ip, True), 
                    "match": mode_match if intent_is_dhcp else profile.interface.ip_address == live_ip
                },
                "gateway": {
                    "staged": profile.interface.gateway or "DHCP", 
                    "live": format_live(live_gw, True), 
                    "match": mode_match if intent_is_dhcp else profile.interface.gateway == live_gw
                },
                "dns_servers": {
                    "staged": profile.interface.dns_servers, 
                    "live": [f"# {d}" for d in live_dns] if (intent_is_dhcp and os_is_dhcp) else live_dns, 
                    "match": mode_match if intent_is_dhcp else set(profile.interface.dns_servers) == set(live_dns)
                }
            },
            "policy_preview": profile.policy.compile(IPParser.parse)
        }