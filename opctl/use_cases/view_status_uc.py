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
        
        # --- OS QUERIES ---
        live_hostname = self.sys_os.get_hostname()
        available_ifaces = self.net_os.get_available_interfaces()
        
        live_dns_set = set()
        for iface in available_ifaces:
            live_dns_set.update(self.net_os.get_dns_servers(iface))
        live_dns = list(live_dns_set)

        # --- BUILD DATA DICTIONARY ---
        # The keys here are literal display names. The StatusReportUseCase will just blindly print them.
        report_data = {
            "System": {
                "Hostname": {
                    "staged": profile.system.hostname or "N/A",
                    "live": live_hostname,
                    "match": profile.system.hostname == live_hostname if profile.system.hostname else False
                },
                "Unmanaged Policy": {
                    "staged": profile.system.unmanaged_policy.title(),
                    "live": "N/A",
                    "match": True # No live OS equivalent to verify against generically yet
                },
                "Global DNS": {
                    "staged": ",".join(profile.network.global_dns) if profile.network.global_dns else "OS Default",
                    "live": ",".join(live_dns) if live_dns else "None",
                    "match": set(profile.network.global_dns) == set(live_dns) if profile.network.global_dns else False
                }
            },
            "NTP": {
                "Enabled": {
                    "staged": str(profile.ntp.enabled),
                    "live": "N/A", 
                    "match": True
                },
                "Servers": {
                    "staged": ",".join(profile.ntp.servers) if profile.ntp.servers else "None",
                    "live": "N/A",
                    "match": True
                }
            },
            "Global Policy": {},
            "Interfaces": {}
        }

        # --- GLOBAL FIREWALL ---
        gp = profile.global_policy.compile(IPParser.parse)
        for v in ["v4", "v6"]:
            report_data["Global Policy"][f"{v.upper()} Targets"] = {"staged": ",".join(gp[v]["targets"]) or "None", "live": "N/A", "match": True}
            report_data["Global Policy"][f"{v.upper()} Trusted"] = {"staged": ",".join(gp[v]["trusted"]) or "None", "live": "N/A", "match": True}
            report_data["Global Policy"][f"{v.upper()} Blocked"] = {"staged": ",".join(gp[v]["blocked"]) or "None", "live": "N/A", "match": True}

        # --- INTERFACES ---
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
            staged_ips = iface_profile.ip_addresses

            lp = iface_profile.policy.compile(IPParser.parse)

            report_data["Interfaces"][iname] = {
                "Admin State": {
                    "staged": "Up" if iface_profile.enabled else "Down",
                    "live": "Up", 
                    "match": True
                },
                "Mode": {
                    "staged": iface_profile.mode.upper(), 
                    "live": "DHCP" if os_is_dhcp else "STATIC", 
                    "match": mode_match
                },
                "MAC Address": {
                    "staged": "Random" if iface_profile.randomize_mac else (iface_profile.mac_address or "Auto"), 
                    "live": live_mac, 
                    "match": iface_profile.mac_address.lower() == live_mac.lower() if iface_profile.mac_address else False
                },
                "IP Address": {
                    "staged": ",".join(staged_ips) if staged_ips else "DHCP", 
                    "live": f"DHCP ({live_ip})" if (intent_is_dhcp and os_is_dhcp) else live_ip, 
                    "match": mode_match if intent_is_dhcp else (live_ip in staged_ips if staged_ips else False)
                },
                "Gateway": {
                    "staged": iface_profile.gateway or "DHCP", 
                    "live": f"DHCP ({live_gw})" if (intent_is_dhcp and os_is_dhcp) else live_gw, 
                    "match": mode_match if intent_is_dhcp else (iface_profile.gateway == live_gw)
                },
                "Local V4 Targets": {"staged": ",".join(lp["v4"]["targets"]) or "None", "live": "N/A", "match": True},
                "Local V4 Trusted": {"staged": ",".join(lp["v4"]["trusted"]) or "None", "live": "N/A", "match": True},
                "Local V4 Blocked": {"staged": ",".join(lp["v4"]["blocked"]) or "None", "live": "N/A", "match": True}
            }

        return report_data