from opctl.domain.models.profile import OpProfile
from opctl.domain.models.interface import InterfaceProfile
from opctl.domain.models.policy import OpPolicy
from opctl.domain.interfaces import IPolicyRepository

class BulkConfigureUseCase:
    def __init__(self, repo: IPolicyRepository):
        self.repo = repo

    @staticmethod
    def _stage_rules(policy, cfg: dict) -> None:
        """Append firewall rules from a config dict keyed by zone name."""
        for zone in OpPolicy.ZONES:
            if zone in cfg:
                values = cfg[zone] if isinstance(cfg[zone], list) else [cfg[zone]]
                for rule in values:
                    policy.add_rule(zone, rule)

    def execute(self, payload: dict) -> None:
        staged_dict = self.repo.load_state()
        profile = OpProfile.from_dict(staged_dict)

        # 1. Global System & Network Config
        if "system" in payload:
            sys_cfg = payload["system"]
            if "hostname" in sys_cfg: profile.system.hostname = sys_cfg["hostname"]
            if "unmanaged" in sys_cfg: profile.system.unmanaged_policy = sys_cfg["unmanaged"]
            # Map DNS to the Network profile (if the shell still sends it under 'system')
            if "dns" in sys_cfg: profile.network.global_dns = sys_cfg["dns"]

        # 2. NTP Config (Future proofing)
        if "ntp" in payload:
            ntp_cfg = payload["ntp"]
            if "servers" in ntp_cfg: profile.ntp.servers = ntp_cfg["servers"]
            if "enable" in ntp_cfg: profile.ntp.enabled = True
            if "disable" in ntp_cfg: profile.ntp.enabled = False

        # 2b. Backend provider selection (per-machine capability)
        if "backend" in payload:
            be_cfg = payload["backend"]
            if "firewall_provider" in be_cfg: profile.backend.firewall_provider = be_cfg["firewall_provider"]
            if "network_provider" in be_cfg: profile.backend.network_provider = be_cfg["network_provider"]
            if "system_provider" in be_cfg: profile.backend.system_provider = be_cfg["system_provider"]
            if "ntp_provider" in be_cfg: profile.backend.ntp_provider = be_cfg["ntp_provider"]

        # 3. Interface-Specific Config & Local Policy
        if "interface_name" in payload:
            iname = payload["interface_name"]
            if iname not in profile.interfaces:
                profile.interfaces[iname] = InterfaceProfile(name=iname)
            
            if "interface_config" in payload:
                iface_cfg = payload["interface_config"]
                if "mode" in iface_cfg: profile.interfaces[iname].mode = iface_cfg["mode"]
                if "ip" in iface_cfg: profile.interfaces[iname].ip_addresses = iface_cfg["ip"]
                if "gateway" in iface_cfg: profile.interfaces[iname].gateway = iface_cfg["gateway"]
                if "dns" in iface_cfg: profile.interfaces[iname].dns_servers = iface_cfg["dns"]
                if "ignore_dns" in iface_cfg: profile.interfaces[iname].dhcp_ignore_dns = True
                
                # Link state toggles
                if "enable" in iface_cfg: profile.interfaces[iname].enabled = True
                if "disable" in iface_cfg: profile.interfaces[iname].enabled = False
                
                if "mac" in iface_cfg:
                    if iface_cfg["mac"].lower() == "random":
                        profile.interfaces[iname].randomize_mac = True
                        profile.interfaces[iname].mac_address = ""
                    else:
                        profile.interfaces[iname].randomize_mac = False
                        profile.interfaces[iname].mac_address = iface_cfg["mac"]

                # Local (per-interface) firewall zone rules
                self._stage_rules(profile.interfaces[iname].policy, iface_cfg)

        # 4. Global firewall zone rules (from `policy` mode)
        if "policy" in payload:
            self._stage_rules(profile.global_policy, payload["policy"])

        self.repo.save_state(profile.to_dict())