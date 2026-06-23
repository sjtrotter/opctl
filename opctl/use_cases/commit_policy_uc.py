from dataclasses import dataclass, field
from typing import Callable, List, Optional

from opctl.domain.models.profile import OpProfile
from opctl.domain.interfaces import (
    IPolicyRepository, ISystemAdapter, INetworkAdapter, IFirewallAdapter, INtpAdapter,
)
from opctl.domain.services.ip_parser import IPParser
from opctl.domain.services.validators import validate_ip, validate_port, validate_interface


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
                 net_os: INetworkAdapter, fw_os: IFirewallAdapter,
                 ntp_os: Optional[INtpAdapter] = None):
        self.repo = repo
        self.sys_os = sys_os
        self.net_os = net_os
        self.fw_os = fw_os
        self.ntp_os = ntp_os

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

        # 1b. NTP time synchronization (host-level identity) — applied before the
        #     firewall/interface churn so a transient link-down can't race it.
        #     NTP is an idempotent, benign host setting and is NOT rolled back: we
        #     can't capture the daemon's full prior state, and restoring with a
        #     guessed enabled-flag could wrongly flip time sync on or off.
        if self.ntp_os is not None and (profile.ntp.servers or profile.ntp.enabled):
            label = ",".join(profile.ntp.servers) or "enabled"
            if not profile.ntp.enabled:
                label += " (disabled)"
            step(f"ntp -> {label}",
                 lambda: self.ntp_os.set_servers(profile.ntp.servers, profile.ntp.enabled))

        # 2. Firewall: reset, then apply the global policy. A single flush undo
        #    removes every managed rule we add (global + per-interface).
        step("firewall: flush managed rules",
             self.fw_os.flush_managed_rules,
             self.fw_os.flush_managed_rules,
             undo_name="flush managed firewall rules")
        # compile() runs inside the step so an invalid staged rule fails the
        # commit (and rolls back) rather than raising before the transaction.
        step("firewall: apply global policy",
             lambda: self._apply_policy(profile.global_policy.compile(IPParser.parse), interface=None))

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

            step(f"{iname}: apply local policy",
                 lambda p=iface.policy, n=iname: self._apply_policy(p.compile(IPParser.parse), interface=n))

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

        # 5. Unmanaged-interface policy — applied to NICs present on the host but not
        #    explicitly configured in the session. 'ignore' (default) does nothing.
        unmanaged_policy = profile.system.unmanaged_policy
        if unmanaged_policy in ("isolate", "disable") and not failed:
            # Enumerate as a tracked step so a query failure SURFACES (and rolls back)
            # rather than silently skipping the sweep — the 'isolate' deny-all is a
            # security posture, so a silent skip would be fail-open.
            available: List[str] = []
            step("unmanaged: enumerate interfaces",
                 lambda: available.extend(self.net_os.get_available_interfaces()))
            # Normalize names so case/whitespace differences (e.g. Windows friendly
            # names) can't misclassify a managed NIC as unmanaged.
            managed = {n.strip().casefold() for n in profile.interfaces}
            for iname in available:
                if iname.strip().casefold() in managed:
                    continue
                if unmanaged_policy == "disable":
                    step(f"unmanaged {iname}: link down",
                         lambda n=iname: self.net_os.set_link_state(n, "down"),
                         lambda n=iname: self.net_os.set_link_state(n, "up"),
                         undo_name=f"bring unmanaged {iname} back up")
                else:  # isolate
                    # Default-deny egress on the unmanaged NIC. The managed-rule flush
                    # undo (step 2) removes these blocks on rollback.
                    step(f"unmanaged {iname}: isolate (deny all egress)",
                         lambda n=iname: self._isolate(n))

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
        # CIDRs are already compiled to real networks, but port overrides ("IP:PORT")
        # and the interface reach the providers raw — and Windows firewall providers
        # build shell=True command strings. Validate them here (inside the tracked
        # step, so bad input fails the commit) to close that injection surface.
        self._validate_fw_inputs(pol, interface)
        self.fw_os.apply_ipv4_blocks(pol["v4"]["blocked"], pol["v4"]["port_blocks"], interface)
        self.fw_os.apply_ipv6_blocks(pol["v6"]["blocked"], pol["v6"]["port_blocks"], interface)
        self.fw_os.apply_ipv4_allows(pol["v4"]["targets"] + pol["v4"]["trusted"], pol["v4"]["port_allows"], interface)
        self.fw_os.apply_ipv6_allows(pol["v6"]["targets"] + pol["v6"]["trusted"], pol["v6"]["port_allows"], interface)

    def _isolate(self, interface: str) -> None:
        """Default-deny: block all egress on an unmanaged interface (v4 + v6)."""
        validate_interface(interface)
        self.fw_os.apply_ipv4_blocks(["0.0.0.0/0"], [], interface)
        self.fw_os.apply_ipv6_blocks(["::/0"], [], interface)

    @staticmethod
    def _validate_fw_inputs(pol: dict, interface: Optional[str]) -> None:
        if interface is not None:
            validate_interface(interface)
        for fam in ("v4", "v6"):
            for entry in pol[fam]["port_blocks"] + pol[fam]["port_allows"]:
                host, _, port = entry.rpartition(":")
                validate_ip(host.strip("[]"))
                validate_port(port)

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
        # Clear any address opctl applied first, so an interface that had no IP
        # before the commit is genuinely returned to no IP. Neither restore
        # branch below fires for a no-IP snapshot, so without this flush a
        # half-applied address from a partial configure_static would survive.
        try:
            self.net_os.flush_addresses(iname)
        except Exception:
            pass
        if snapshot.get("dhcp"):
            self.net_os.configure_dhcp(iname)
        elif snapshot.get("ip") and snapshot["ip"] not in ("Unassigned", "N/A", "Unknown"):
            self.net_os.configure_static(
                iname, snapshot["ip"], snapshot.get("gateway") or "", snapshot.get("dns") or [],
            )
        if snapshot.get("mac") and snapshot["mac"] not in ("N/A", "Unknown"):
            self.net_os.set_mac_address(iname, snapshot["mac"])
        self.net_os.set_link_state(iname, "up")
