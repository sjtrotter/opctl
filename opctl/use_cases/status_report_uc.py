from typing import List
from .view_status_uc import ViewStatusUseCase
from ..domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class StatusReportUseCase:
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.view_status = ViewStatusUseCase(repo, sys_os, net_os)

    def _format_row(self, prop: str, staged: str, live: str, match: bool) -> str:
        staged_str = str(staged)[:25]
        live_str = str(live)[:25]
        status_text = f"{Colors.GREEN}[ SYNC ]{Colors.RESET}" if match else f"{Colors.RED}[ DIFF ]{Colors.RESET}"
        return f"{prop:<18} {staged_str:<25} {live_str:<25} {status_text}"

    def execute(self) -> List[str]:
        data = self.view_status.execute()
        header = f"{'PROPERTY':<18} {'STAGED':<25} {'LIVE':<25} STATUS"
        lines: List[str] = []

        # --- GLOBAL SYSTEM SECTION ---
        lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ GLOBAL SYSTEM ] ==={Colors.RESET}")
        lines.append(header); lines.append("-" * 80)
        
        sys = data["identity"]
        lines.append(self._format_row("Hostname", sys['hostname']['staged'] or "N/A", sys['hostname']['live'], sys['hostname']['match']))
        
        staged_dns = ",".join(sys['dns_servers']['staged']) if sys['dns_servers']['staged'] else "OS Default"
        live_dns = ",".join(sys['dns_servers']['live']) if sys['dns_servers']['live'] else "None"
        lines.append(self._format_row("DNS Servers", staged_dns, live_dns, sys['dns_servers']['match']))

        # --- INTERFACE LOOP ---
        for iface_name, iface in data["interfaces"].items():
            lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ INTERFACE: {iface_name} ] ==={Colors.RESET}")
            lines.append(header); lines.append("-" * 80)
            
            lines.append(self._format_row("Config Mode", iface['mode']['staged'], iface['mode']['live'], iface['mode']['match']))
            lines.append(self._format_row("MAC Address", iface['mac_address']['staged'], iface['mac_address']['live'], iface['mac_address']['match']))
            
            # Print Local Policy if it exists
            local_pol = iface["local_policy_preview"]["v4"]
            if local_pol["targets"] or local_pol["trusted"] or local_pol["blocked"]:
                lines.append("-" * 80)
                lines.append(f"{Colors.BOLD}LOCAL FIREWALL (v4){Colors.RESET}")
                lines.append(f"  Targets : {','.join(local_pol['targets']) or 'None'}")
                lines.append(f"  Trusted : {','.join(local_pol['trusted']) or 'None'}")
                lines.append(f"  Blocked : {','.join(local_pol['blocked']) or 'None'}")

        # --- GLOBAL FIREWALL SECTION ---
        lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ GLOBAL FIREWALL PREVIEW ] ==={Colors.RESET}")
        p = data["global_policy_preview"]
        for v in ["v4", "v6"]:
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Targets : {','.join(p[v]['targets']) or 'None'}")
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Trusted : {','.join(p[v]['trusted']) or 'None'}")
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Blocked : {','.join(p[v]['blocked']) or 'None'}")
        
        lines.append("") 
        return lines