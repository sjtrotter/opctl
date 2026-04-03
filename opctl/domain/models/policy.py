import ipaddress
from typing import Set, List, Dict, Union, Tuple

class OpPolicy:
    """
    The declarative domain model for the workstation's network policy.
    Maintains the raw rules and handles the IPv4/IPv6 network compilation math.
    """
    def __init__(self):
        self.raw_trusted: Set[str] = set()
        self.raw_targets: Set[str] = set()
        self.raw_excluded: Set[str] = set()

    def add_rule(self, zone: str, rule: str) -> None:
        """Stages a new rule string into the correct zone."""
        if zone == "trusted":
            self.raw_trusted.add(rule)
        elif zone == "target":
            self.raw_targets.add(rule)
        elif zone == "excluded":
            self.raw_excluded.add(rule)

    def remove_rule(self, zone: str, rule: str) -> None:
        """Removes a rule string from the correct zone. Uses discard to prevent KeyErrors."""
        if zone == "trusted":
            self.raw_trusted.discard(rule)
        elif zone == "target":
            self.raw_targets.discard(rule)
        elif zone == "excluded":
            self.raw_excluded.discard(rule)

    def compile(self, parse_strategy) -> Dict[str, Dict[str, List[str]]]:
        """
        Translates raw strings, applies the safety valve network subtraction, 
        and returns segregated IPv4/IPv6 minimal CIDR blocks and explicit port overrides.
        """
        # 1. Strip out specific Layer 4 Port overrides from all buckets
        pure_trust, port_trust = self._split_ports(self.raw_trusted)
        pure_target, port_target = self._split_ports(self.raw_targets)
        pure_exclude, port_exclude = self._split_ports(self.raw_excluded)

        # 2. Parse the pure IPs into Network objects
        trusted_nets = self._parse_to_networks(pure_trust, parse_strategy)
        target_nets = self._parse_to_networks(pure_target, parse_strategy)
        excluded_nets = self._parse_to_networks(pure_exclude, parse_strategy)

        # 3. Apply Safety Valve Subtraction (Layer 3 Math)
        clean_trusted = self._subtract_networks(trusted_nets, excluded_nets)
        clean_targets = self._subtract_networks(target_nets, excluded_nets)
        
        # 4. Group the Layer 4 ports by Protocol Version
        all_port_allows = port_trust + port_target
        
        v4_allow_ports = [p for p in all_port_allows if '.' in p]
        v6_allow_ports = [p for p in all_port_allows if ']' in p]
        v4_block_ports = [p for p in port_exclude if '.' in p]
        v6_block_ports = [p for p in port_exclude if ']' in p]

        return {
            "v4": {
                "trusted": self._collapse(clean_trusted, version=4),
                "targets": self._collapse(clean_targets, version=4),
                "blocked": self._collapse(excluded_nets, version=4),
                "port_blocks": v4_block_ports,
                "port_allows": v4_allow_ports
            },
            "v6": {
                "trusted": self._collapse(clean_trusted, version=6),
                "targets": self._collapse(clean_targets, version=6),
                "blocked": self._collapse(excluded_nets, version=6),
                "port_blocks": v6_block_ports,
                "port_allows": v6_allow_ports
            }
        }

    def _split_ports(self, raw_set: Set[str]) -> Tuple[Set[str], List[str]]:
        """Separates pure IP/CIDR blocks from rules containing specific port designations."""
        pure_ips = set()
        port_overrides = []
        for rule in raw_set:
            # IPv4 specific port notation (e.g. 192.168.1.1:443)
            if rule.count(':') == 1 and '.' in rule:
                port_overrides.append(rule)
            # IPv6 specific port notation (e.g. [2001:db8::1]:80)
            elif ']:' in rule:
                port_overrides.append(rule)
            else:
                pure_ips.add(rule)
        return pure_ips, port_overrides

    def _parse_to_networks(self, raw_set: Set[str], parse_strategy) -> Set[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        net_set = set()
        for raw_str in raw_set:
            net_set.update(parse_strategy(raw_str))
        return net_set

    def _subtract_networks(self, allowed: Set, excluded: Set) -> Set:
        """Mathematically cuts excluded subnets out of allowed subnets."""
        final_nets = set(allowed)
        
        for ex_net in excluded:
            new_final = set()
            for al_net in final_nets:
                # Do not attempt to overlap IPv4 and IPv6
                if al_net.version != ex_net.version:
                    new_final.add(al_net)
                    continue
                    
                if al_net.overlaps(ex_net):
                    try:
                        # address_exclude shatters the network around the exclusion
                        new_final.update(list(al_net.address_exclude(ex_net)))
                    except ValueError:
                        # If the excluded network completely encompasses the allowed network
                        pass 
                else:
                    new_final.add(al_net)
            final_nets = new_final
            
        return final_nets

    def _collapse(self, networks: Set, version: int) -> List[str]:
        """Filters by protocol version and collapses into minimal CIDR strings."""
        filtered = {n for n in networks if n.version == version}
        return [str(net) for net in ipaddress.collapse_addresses(filtered)]