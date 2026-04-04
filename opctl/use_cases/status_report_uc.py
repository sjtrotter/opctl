from typing import List
from .view_status_uc import ViewStatusUseCase
from ..domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter

class StatusReportUseCase:
    """Orchestrates the generation of a human-friendly KV status report."""
    
    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.view_status = ViewStatusUseCase(repo, sys_os, net_os)

    def execute(self) -> List[str]:
        data = self.view_status.execute()
        lines: List[str] = ["--- [ IDENTITY ] ---"]
        
        host = data["identity"]["hostname"]
        lines.append(f"hostname.staged        : {host['staged']}")
        lines.append(f"hostname.live          : {host['live']}")
        lines.append(f"hostname.match         : {host['match']}")

        iface = data["interface"]
        lines.append(f"\n--- [ INTERFACE: {iface['name']} ] ---")
        lines.append(f"interface.mode         : {iface['mode']['staged']} (Live: {iface['mode']['live']})")
        lines.append(f"interface.mode_match   : {iface['mode']['match']}")

        mac = iface["mac_address"]
        lines.append(f"interface.mac.staged   : {mac['staged']}")
        lines.append(f"interface.mac.live     : {mac['live']}")
        lines.append(f"interface.mac.match    : {mac['match']}")

        for field in ["ip_address", "gateway"]:
            val = iface[field]
            key = field.replace("_address", "").replace("gateway", "gw")
            lines.append(f"interface.{key}.staged    : {val['staged']}")
            lines.append(f"interface.{key}.live      : {val['live']}")
            lines.append(f"interface.{key}.match     : {val['match']}")

        dns = iface["dns_servers"]
        lines.append(f"interface.dns.staged   : {','.join(dns['staged']) if dns['staged'] else '[]'}")
        lines.append(f"interface.dns.live     : {','.join(dns['live']) if dns['live'] else '[]'}")
        lines.append(f"interface.dns.match    : {dns['match']}")

        lines.append("\n--- [ POLICY PREVIEW ] ---")
        p = data["policy_preview"]
        for v in ["v4", "v6"]:
            lines.append(f"{v}.trusted         : {','.join(p[v]['trusted']) or 'None'}")
            lines.append(f"{v}.targets         : {','.join(p[v]['targets']) or 'None'}")
            lines.append(f"{v}.blocked         : {','.join(p[v]['blocked']) or 'None'}")
        
        return lines