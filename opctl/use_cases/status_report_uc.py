from typing import List, Optional
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
        return f"{prop:<20} {staged_str:<25} {live_str:<25} {status_text}"

    def execute(self, mode: str = "root", target_interface: Optional[str] = None) -> List[str]:
        data = self.view_status.execute()
        header = f"{'PROPERTY':<20} {'STAGED':<25} {'LIVE':<25} STATUS"
        lines: List[str] = []

        def print_section(title, section_data):
            lines.append(f"\n{Colors.BOLD}{Colors.CYAN}=== [ {title.upper()} ] ==={Colors.RESET}")
            lines.append(header); lines.append("-" * 82)
            for key, val in section_data.items():
                lines.append(self._format_row(key, val["staged"], val["live"], val["match"]))

        # Context-Aware Rendering
        if mode in ["root", "system", "configure"]:
            print_section("Global System", data["System"])
            
        if mode in ["root", "ntp", "configure"]:
            print_section("NTP Services", data["NTP"])

        if mode in ["root", "policy", "configure"]:
            print_section("Global Firewall", data["Global Policy"])

        if mode in ["root", "interface", "configure"]:
            for iface_name, iface_data in data["Interfaces"].items():
                # Filter specific interface if requested
                if target_interface and iface_name != target_interface:
                    continue
                print_section(f"Interface: {iface_name}", iface_data)

        if not lines:
            lines.append("[*] No staged configurations found for this context.")
            
        lines.append("") 
        return lines