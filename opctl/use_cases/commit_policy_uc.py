from dataclasses import dataclass, field
from typing import Callable, List, Optional

from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import IPolicyRepository, ISystemAdapter, INetworkAdapter, IFirewallAdapter
from opctl.domain.services.ip_parser import IPParser


@dataclass
class CommitStep:
    """The outcome of a single commit (or rollback) action."""
    name: str
    status: str            # "ok" | "failed" | "skipped"
    detail: str = ""


@dataclass
class CommitReport:
    """The result of a commit attempt: every step, plus any rollback."""
    steps: List[CommitStep] = field(default_factory=list)
    rolled_back: bool = False
    rollback_steps: List[CommitStep] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(s.status != "failed" for s in self.steps)


class CommitPolicyUseCase:
    """Commits staged config to hardware as a tracked, best-effort-reversible transaction.

    Each adapter action is recorded as a CommitStep. On the first failure, remaining
    steps are skipped and the use case rolls back — in reverse order — the actions that
    already succeeded, restoring a live snapshot taken before the commit began. The
    returned CommitReport tells the operator exactly what was applied, what failed, and
    what was restored, so the system is never left in a silently half-applied state.

    Rollback is best-effort: it is bounded by what the adapter ports can read back and
    re-apply (e.g. a live IP is read without its prefix length), so it restores as
    closely as the OS layer allows and reports any restore step it could not complete.
    """

    def __init__(self, repo: IPolicyRepository, sys_os: ISystemAdapter,
                 net_os: INetworkAdapter, fw_os: IFirewallAdapter):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os
        self.fw_os = fw_os

    def execute(self) -> CommitReport:
        profile = OpProfile.from_dict(self.repo.load_state())
        report = CommitReport()
        undo: List[tuple] = []          # (label, callable) pushed as each step succeeds
        failed = False

        def step(name: str, action: Callable[[], None],
                 undo_action: Optional[Callable[[], None]] = None,
                 undo_name: Optional[str] = None) -> None:
            nonlocal failed
            if failed:
                report.steps.append(CommitStep(name, "skipped"))
                return
            try:
                action()
                report.steps.append(CommitStep(name, "ok"))
                if undo_action is not None:
                    undo.append((undo_name or name, undo_action))
            except Exception as e:
                report.steps.append(CommitStep(name, "failed", str(e)))
                failed = True

        # 1. System identity
        if profile.system.hostname:
            old_hostname = self._capture(self.sys_os.get_hostname)
            step(
                f"hostname -> {profile.system.hostname}",
                lambda: self.sys_os.set_hostname(profile.system.hostname),
                (lambda o=old_hostname: self.sys_os.set_hostname(o)) if old_hostname else None,
                undo_name=f"restore hostname -> {old_hostname}",
            )

        # 2. Firewall: reset, then apply the global policy. A single flush undo
        #    removes every managed rule we add (global + per-interface).
        step("firewall: flush managed rules",
             self.fw_os.flush_managed_rules,
             self.fw_os.flush_managed_rules,
             undo_name="flush managed firewall rules")
        global_pol = profile.global_policy.compile(IPParser.parse)
        step("firewall: apply global policy",
             lambda: self._apply_policy(global_pol, interface=None))

        # 3. Per-interface configuration
        for iname, iface in profile.interfaces.items():
            if not iface.enabled:
                step(f"{iname}: link down",
                     lambda n=iname: self.net_os.set_link_state(n, "down"),
                     lambda n=iname: self.net_os.set_link_state(n, "up"),
                     undo_name=f"bring {iname} back up")
                continue

            snapshot = self._snapshot_iface(iname)
            # The first mutation of this interface registers a single undo that
            # restores the whole interface from its pre-commit snapshot.
            step(f"{iname}: link down",
                 lambda n=iname: self.net_os.set_link_state(n, "down"),
                 lambda n=iname, s=snapshot: self._restore_iface(n, s),
                 undo_name=f"restore {iname} from snapshot")

            if iface.mac_address:
                step(f"{iname}: set MAC {iface.mac_address}",
                     lambda n=iname, m=iface.mac_address: self.net_os.set_mac_address(n, m))

            local_pol = iface.policy.compile(IPParser.parse)
            step(f"{iname}: apply local policy",
                 lambda lp=local_pol, n=iname: self._apply_policy(lp, interface=n))

            if iface.is_static():
                primary_ip = iface.ip_addresses[0] if iface.ip_addresses else ""
                step(f"{iname}: configure static {primary_ip}".rstrip(),
                     lambda n=iname, ip=primary_ip, g=iface.gateway, d=iface.dns_servers:
                         self.net_os.configure_static(n, ip, g, d))
            else:
                step(f"{iname}: configure dhcp",
                     lambda n=iname: self.net_os.configure_dhcp(n))

            step(f"{iname}: link up",
                 lambda n=iname: self.net_os.set_link_state(n, "up"))

        if failed:
            report.rolled_back = True
            for name, undo_action in reversed(undo):
                try:
                    undo_action()
                    report.rollback_steps.append(CommitStep(name, "ok"))
                except Exception as e:
                    report.rollback_steps.append(CommitStep(name, "failed", str(e)))

        return report

    # --- helpers ---------------------------------------------------------

    def _apply_policy(self, pol: dict, interface: Optional[str]) -> None:
        self.fw_os.apply_ipv4_blocks(pol["v4"]["blocked"], pol["v4"]["port_blocks"], interface)
        self.fw_os.apply_ipv6_blocks(pol["v6"]["blocked"], pol["v6"]["port_blocks"], interface)
        self.fw_os.apply_ipv4_allows(pol["v4"]["targets"] + pol["v4"]["trusted"], pol["v4"]["port_allows"], interface)
        self.fw_os.apply_ipv6_allows(pol["v6"]["targets"] + pol["v6"]["trusted"], pol["v6"]["port_allows"], interface)

    @staticmethod
    def _capture(getter: Callable, *args):
        """Read a live value for the rollback snapshot, tolerating query failures."""
        try:
            return getter(*args)
        except Exception:
            return None

    def _snapshot_iface(self, iname: str) -> dict:
        return {
            "mac": self._capture(self.net_os.get_mac_address, iname),
            "dhcp": self._capture(self.net_os.is_dhcp_enabled, iname),
            "ip": self._capture(self.net_os.get_ip_address, iname),
            "gateway": self._capture(self.net_os.get_gateway, iname),
            "dns": self._capture(self.net_os.get_dns_servers, iname),
        }

    def _restore_iface(self, iname: str, snapshot: dict) -> None:
        """Best-effort restore of an interface to its pre-commit snapshot."""
        self.net_os.set_link_state(iname, "down")
        if snapshot.get("dhcp"):
            self.net_os.configure_dhcp(iname)
        elif snapshot.get("ip") and snapshot["ip"] not in ("Unassigned", "N/A", "Unknown"):
            self.net_os.configure_static(
                iname, snapshot["ip"], snapshot.get("gateway") or "", snapshot.get("dns") or [],
            )
        if snapshot.get("mac") and snapshot["mac"] not in ("N/A", "Unknown"):
            self.net_os.set_mac_address(iname, snapshot["mac"])
        self.net_os.set_link_state(iname, "up")
