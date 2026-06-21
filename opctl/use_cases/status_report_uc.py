from typing import List, Optional, Dict
from .view_status_uc import ViewStatusUseCase
from ..domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class StatusReportUseCase:
    """Renders the staged-vs-live comparison as a diff-first report.

    Changes (what `execute` will apply) lead, followed by fields already in sync,
    then staged-only fields that have no live counterpart. Fields that are not
    configured are omitted entirely.
    """

    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter, net_os: INetworkAdapter):
        self.view_status = ViewStatusUseCase(repo, sys_os, net_os)

    def execute(self, mode: str = "root", target_interface: Optional[str] = None) -> List[str]:
        data = self.view_status.execute()
        rows = self._collect(data, mode, target_interface)

        if not rows:
            return ["", "[*] No staged configuration for this context.", ""]

        changed = [r for r in rows if r["state"] == "changed"]
        synced = [r for r in rows if r["state"] == "synced"]
        staged = [r for r in rows if r["state"] == "staged"]

        # Column widths shared across groups so everything lines up.
        sec_w = max(len(r["section"]) for r in rows)
        fld_w = max(len(r["field"]) for r in rows)
        live_w = max((len(str(r["live"])) for r in changed), default=0)

        lines: List[str] = [
            "",
            f"{Colors.BOLD}opctl · staged vs live{Colors.RESET}   "
            f"{Colors.YELLOW}{len(changed)} change{Colors.RESET} · "
            f"{Colors.GREEN}{len(synced)} in sync{Colors.RESET} · "
            f"{Colors.CYAN}{len(staged)} staged{Colors.RESET}",
        ]

        if changed:
            lines.append("")
            lines.append(f"{Colors.BOLD}{Colors.YELLOW}CHANGES{Colors.RESET}  (apply with `execute`)")
            for r in changed:
                lines.append(
                    f"  {r['section']:<{sec_w}}  {r['field']:<{fld_w}}  "
                    f"{str(r['live']):<{live_w}} {Colors.YELLOW}->{Colors.RESET} {r['staged']}"
                )

        if synced:
            lines.append("")
            lines.append(f"{Colors.BOLD}{Colors.GREEN}IN SYNC{Colors.RESET}")
            for r in synced:
                lines.append(f"  {r['section']:<{sec_w}}  {r['field']:<{fld_w}}  {r['staged']}")

        if staged:
            lines.append("")
            lines.append(f"{Colors.BOLD}{Colors.CYAN}STAGED{Colors.RESET}  (no live value to compare)")
            for r in staged:
                lines.append(f"  {r['section']:<{sec_w}}  {r['field']:<{fld_w}}  {r['staged']}")

        lines.append("")
        return lines

    def _collect(self, data: dict, mode: str, target_interface: Optional[str]) -> List[Dict]:
        rows: List[Dict] = []

        def add(section: str, fields: dict) -> None:
            for field_label, info in fields.items():
                if info.get("state", "unset") == "unset":
                    continue
                rows.append({
                    "section": section,
                    "field": field_label.lower(),
                    "staged": info["staged"],
                    "live": info["live"],
                    "state": info["state"],
                })

        if mode in ("root", "system", "configure"):
            add("system", data["System"])
        if mode in ("root", "ntp", "configure"):
            add("ntp", data["NTP"])
        if mode in ("root", "backend", "configure"):
            add("backend", data["Backend"])
        if mode in ("root", "policy", "configure"):
            add("firewall", data["Global Policy"])
        if mode in ("root", "interface", "configure"):
            for iname, fields in data["Interfaces"].items():
                if target_interface and iname != target_interface:
                    continue
                add(iname, fields)

        return rows
