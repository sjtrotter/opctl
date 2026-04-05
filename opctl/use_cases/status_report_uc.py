from typing import List
from .view_status_uc import ViewStatusUseCase
from ..domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter

class Colors:
    """Standard ANSI escape codes for terminal colors."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class StatusReportUseCase:
    """Orchestrates the generation of a human-friendly, colorized tabular status report."""
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.view_status = ViewStatusUseCase(repo, sys_os, net_os)

    def _format_row(self, prop: str, staged: str, live: str, match: bool) -> str:
            staged_str = str(staged)[:25]
            live_str = str(live)[:25]
            status_text = f"{Colors.GREEN}[ SYNC ]{Colors.RESET}" if match else f"{Colors.RED}[ DIFF ]{Colors.RESET}"
            
            # Whitespace padded, no pipes
            return f"{prop:<18} {staged_str:<25} {live_str:<25} {status_text}"

    def execute(self) -> List[str]:
        data = self.view_status.execute()
        header = f"{'PROPERTY':<18} {'STAGED':<25} {'LIVE':<25} STATUS"
        lines: List[str] = []

        # --- IDENTITY SECTION ---
        lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ IDENTITY ] ==={Colors.RESET}")
        lines.append(header)
        lines.append("-" * 80)
        
        host = data["identity"]["hostname"]
        lines.append(self._format_row("Hostname", host['staged'] or "N/A", host['live'], host['match']))

        # --- INTERFACE SECTION ---
        iface = data["interface"]
        lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ INTERFACE: {iface['name']} ] ==={Colors.RESET}")
        lines.append(header)
        lines.append("-" * 80)
        
        # Mode
        lines.append(self._format_row("Config Mode", iface['mode']['staged'], iface['mode']['live'], iface['mode']['match']))
        
        # MAC
        mac = iface["mac_address"]
        lines.append(self._format_row("MAC Address", mac['staged'], mac['live'], mac['match']))

        # L3 Properties
        for field, display_name in [("ip_address", "IP Address"), ("gateway", "Gateway")]:
            val = iface[field]
            # Clean up the output if we are using DHCP logic from ViewStatus
            staged_val = str(val['staged'])
            live_val = str(val['live']).replace("DHCP (# ", "").replace(")", "") # Strip the old comment logic for the table
            lines.append(self._format_row(display_name, staged_val, live_val, val['match']))

        # DNS
        dns = iface["dns_servers"]
        staged_dns = ",".join(dns['staged']) if dns['staged'] else "DHCP" if iface['mode']['staged'] == 'dhcp' else "[]"
        live_dns = ",".join([d.replace("# ", "") for d in dns['live']]) if dns['live'] else "None"
        lines.append(self._format_row("DNS Servers", staged_dns, live_dns, dns['match']))

        # --- POLICY SECTION ---
        lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ POLICY PREVIEW ] ==={Colors.RESET}")
        p = data["policy_preview"]
        for v in ["v4", "v6"]:
            trusted = ",".join(p[v]['trusted']) or 'None'
            targets = ",".join(p[v]['targets']) or 'None'
            blocked = ",".join(p[v]['blocked']) or 'None'
            
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Trusted : {trusted}")
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Targets : {targets}")
            lines.append(f"{Colors.BOLD}{v.upper()}{Colors.RESET} Blocked : {blocked}")
        
        lines.append("") # Trailing newline
        return lines