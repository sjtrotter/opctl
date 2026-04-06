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
        
        # --- GLOBAL SYSTEM STATUS ---
        live_hostname = self.sys_os.get_hostname()
        
        # Aggregate live DNS from all available OS interfaces
        available_ifaces = self.net_os.get_available_interfaces()
        live_dns_set = set()
        for iface in available_ifaces:
            live_dns_set.update(self.net_os.get_dns_servers(iface))
        live_dns = list(live_dns_set)

        # --- INTERFACE LOOP ---
        interfaces_status = {}
        for iname, iface_profile in profile.interfaces.items():
            live_mac, live_ip, live_gw = "N/A", "Unassigned", "None"
            os_is_dhcp = False

            if iname in available_ifaces:
                live_mac = self.net_os.get_mac_address(iname)
                live_ip = self.net_os.get_ip_address(iname)
                live_gw = self.net_os.get_gateway(iname)
                os_is_dhcp = self.net_os.is_dhcp_enabled(iname)

            intent_is_dhcp = iface_profile.mode.lower() == "dhcp"
            mode_match = (intent_is_dhcp == os_is_dhcp)

            def format_live(val: str, is_dhcp_context: bool) -> str:
                if intent_is_dhcp and is_dhcp_context and os_is_dhcp:
                    return f"DHCP (# {val})"
                return val

            staged_ips = iface_profile.ip_addresses
            ip_match = mode_match if intent_is_dhcp else (live_ip in staged_ips if staged_ips else False)

            interfaces_status[iname] = {
                "name": iname,
                "admin_state": {
                    "staged": "Up" if iface_profile.enabled else "Down",
                    "live": "Up", # Assumes Up unless link state queried directly
                    "match": True
                },
                "mode": {
                    "staged": iface_profile.mode, 
                    "live": "dhcp" if os_is_dhcp else "static", 
                    "match": mode_match
                },
                "mac_address": {
                    "staged": "Random" if iface_profile.randomize_mac else (iface_profile.mac_address or "Auto"), 
                    "live": live_mac, 
                    "match": iface_profile.mac_address.lower() == live_mac.lower() if iface_profile.mac_address else False
                },
                "ip_address": {
                    "staged": ",".join(staged_ips) if staged_ips else "DHCP", 
                    "live": format_live(live_ip, True), 
                    "match": ip_match
                },
                "gateway": {
                    "staged": iface_profile.gateway or "DHCP", 
                    "live": format_live(live_gw, True), 
                    "match": mode_match if intent_is_dhcp else (iface_profile.gateway == live_gw)
                },
                "local_policy_preview": iface_profile.policy.compile(IPParser.parse)
            }

        return {
            "identity": {
                "hostname": {
                    "staged": profile.system.hostname,
                    "live": live_hostname,
                    "match": profile.system.hostname == live_hostname if profile.system.hostname else False
                },
                "dns_servers": {
                    "staged": profile.network.global_dns,
                    "live": live_dns,
                    "match": set(profile.network.global_dns) == set(live_dns) if profile.network.global_dns else False
                }
            },
            "interfaces": interfaces_status,
            "global_policy_preview": profile.global_policy.compile(IPParser.parse)
        }