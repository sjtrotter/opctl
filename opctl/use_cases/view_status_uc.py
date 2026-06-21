from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter
from opctl.domain.services.ip_parser import IPParser


class ViewStatusUseCase:
    """Builds the staged-vs-live comparison data.

    Every field carries a ``state`` so the presenter can render honestly:
      - ``changed`` — has a live value that differs from the staged intent
      - ``synced``  — has a live value equal to the staged intent
      - ``staged``  — staged, but there is no live equivalent to compare against
      - ``unset``   — not configured; nothing to show
    """

    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os

    @staticmethod
    def _field(staged, live, *, comparable: bool, present: bool, match: bool = False) -> dict:
        if not present:
            state = "unset"
        elif not comparable:
            state = "staged"
        else:
            state = "synced" if match else "changed"
        return {"staged": staged, "live": live, "match": bool(match), "state": state}

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

        report_data = {
            "System": {
                "Hostname": self._field(
                    profile.system.hostname or "N/A", live_hostname,
                    comparable=True, present=bool(profile.system.hostname),
                    match=profile.system.hostname == live_hostname,
                ),
                "Unmanaged Policy": self._field(
                    profile.system.unmanaged_policy.title(), "N/A",
                    comparable=False, present=profile.system.unmanaged_policy != "ignore",
                ),
                "Global DNS": self._field(
                    ",".join(profile.network.global_dns) if profile.network.global_dns else "OS Default",
                    ",".join(live_dns) if live_dns else "None",
                    comparable=True, present=bool(profile.network.global_dns),
                    match=set(profile.network.global_dns) == set(live_dns),
                ),
            },
            "NTP": {
                "Enabled": self._field(
                    str(profile.ntp.enabled), "N/A",
                    comparable=False, present=profile.ntp.enabled,
                ),
                "Servers": self._field(
                    ",".join(profile.ntp.servers) if profile.ntp.servers else "None", "N/A",
                    comparable=False, present=bool(profile.ntp.servers),
                ),
            },
            "Backend": {
                "Firewall Provider": self._field(
                    profile.backend.firewall_provider, "N/A",
                    comparable=False, present=profile.backend.firewall_provider != "auto"),
                "Network Provider": self._field(
                    profile.backend.network_provider, "N/A",
                    comparable=False, present=profile.backend.network_provider != "auto"),
                "System Provider": self._field(
                    profile.backend.system_provider, "N/A",
                    comparable=False, present=profile.backend.system_provider != "auto"),
            },
            "Global Policy": {},
            "Interfaces": {},
        }

        # --- GLOBAL FIREWALL (staged-only: no generic live equivalent) ---
        gp = profile.global_policy.compile(IPParser.parse)
        for v in ["v4", "v6"]:
            for cat in ["targets", "trusted", "blocked"]:
                rules = gp[v][cat]
                report_data["Global Policy"][f"{v.upper()} {cat.title()}"] = self._field(
                    ",".join(rules) if rules else "None", "N/A",
                    comparable=False, present=bool(rules),
                )

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
            has_mac_intent = iface_profile.randomize_mac or bool(iface_profile.mac_address)

            lp = iface_profile.policy.compile(IPParser.parse)

            iface_fields = {
                "Admin State": self._field(
                    "Up" if iface_profile.enabled else "Down", "Up",
                    comparable=True, present=True, match=iface_profile.enabled,
                ),
                "Mode": self._field(
                    iface_profile.mode.upper(), "DHCP" if os_is_dhcp else "STATIC",
                    comparable=True, present=True, match=mode_match,
                ),
                "MAC Address": self._field(
                    "Random" if iface_profile.randomize_mac else (iface_profile.mac_address or "Auto"),
                    live_mac,
                    comparable=True, present=has_mac_intent,
                    match=iface_profile.mac_address.lower() == live_mac.lower() if iface_profile.mac_address else False,
                ),
                "IP Address": self._field(
                    ",".join(staged_ips) if staged_ips else "DHCP",
                    f"DHCP ({live_ip})" if (intent_is_dhcp and os_is_dhcp) else live_ip,
                    comparable=True, present=True,
                    match=mode_match if intent_is_dhcp else (live_ip in staged_ips if staged_ips else False),
                ),
                "Gateway": self._field(
                    iface_profile.gateway or "DHCP",
                    f"DHCP ({live_gw})" if (intent_is_dhcp and os_is_dhcp) else live_gw,
                    comparable=True, present=intent_is_dhcp or bool(iface_profile.gateway),
                    match=mode_match if intent_is_dhcp else (iface_profile.gateway == live_gw),
                ),
            }
            for cat in ["targets", "trusted", "blocked"]:
                rules = lp["v4"][cat]
                iface_fields[f"Local V4 {cat.title()}"] = self._field(
                    ",".join(rules) if rules else "None", "N/A",
                    comparable=False, present=bool(rules),
                )

            report_data["Interfaces"][iname] = iface_fields

        return report_data
