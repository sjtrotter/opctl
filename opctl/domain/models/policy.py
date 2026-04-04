import ipaddress
from typing import Set, List, Dict, Union, Tuple, Callable, Iterable, AbstractSet, cast

NetworkObject = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

class OpPolicy:
    def __init__(self) -> None:
        self.raw_trusted: Set[str] = set()
        self.raw_targets: Set[str] = set()
        self.raw_excluded: Set[str] = set()

    def add_rule(self, zone: str, rule: str) -> None:
        if zone == "trusted": self.raw_trusted.add(rule)
        elif zone == "target": self.raw_targets.add(rule)
        elif zone == "excluded": self.raw_excluded.add(rule)

    def remove_rule(self, zone: str, rule: str) -> None:
        if zone == "trusted": self.raw_trusted.discard(rule)
        elif zone == "target": self.raw_targets.discard(rule)
        elif zone == "excluded": self.raw_excluded.discard(rule)

    def compile(self, parse_strategy: Callable[[str], Iterable[NetworkObject]]) -> Dict[str, Dict[str, List[str]]]:
        pure_trust, port_trust = self._split_ports(self.raw_trusted)
        pure_target, port_target = self._split_ports(self.raw_targets)
        pure_exclude, port_exclude = self._split_ports(self.raw_excluded)

        trusted_nets = self._parse_to_networks(pure_trust, parse_strategy)
        target_nets = self._parse_to_networks(pure_target, parse_strategy)
        excluded_nets = self._parse_to_networks(pure_exclude, parse_strategy)

        clean_trusted = self._subtract_networks(trusted_nets, excluded_nets)
        clean_targets = self._subtract_networks(target_nets, excluded_nets)
        
        all_port_allows = port_trust + port_target
        
        return {
            "v4": {
                "trusted": self._collapse(clean_trusted, 4),
                "targets": self._collapse(clean_targets, 4),
                "blocked": self._collapse(excluded_nets, 4),
                "port_blocks": [p for p in port_exclude if '.' in p],
                "port_allows": [p for p in all_port_allows if '.' in p]
            },
            "v6": {
                "trusted": self._collapse(clean_trusted, 6),
                "targets": self._collapse(clean_targets, 6),
                "blocked": self._collapse(excluded_nets, 6),
                "port_blocks": [p for p in port_exclude if ']' in p],
                "port_allows": [p for p in all_port_allows if ']' in p]
            }
        }

    def _split_ports(self, raw_set: AbstractSet[str]) -> Tuple[Set[str], List[str]]:
        pure_ips: Set[str] = set()
        ports: List[str] = []
        for r in raw_set:
            if (r.count(':') == 1 and '.' in r) or ']:' in r:
                ports.append(r)
            else:
                pure_ips.add(r)
        return pure_ips, ports

    def _parse_to_networks(self, raw_set: Iterable[str], strategy: Callable[[str], Iterable[NetworkObject]]) -> Set[NetworkObject]:
        nets: Set[NetworkObject] = set()
        for s in raw_set:
            nets.update(strategy(s))
        return nets

    def _subtract_networks(self, allowed: AbstractSet[NetworkObject], excluded: AbstractSet[NetworkObject]) -> Set[NetworkObject]:
        final: Set[NetworkObject] = set(allowed)
        for ex in excluded:
            temp: Set[NetworkObject] = set()
            for al in final:
                if al.version == ex.version and al.overlaps(ex):
                    try:
                        # Explicitly cast to prove both are same version for address_exclude
                        if isinstance(al, ipaddress.IPv4Network) and isinstance(ex, ipaddress.IPv4Network):
                            temp.update(al.address_exclude(ex))
                        elif isinstance(al, ipaddress.IPv6Network) and isinstance(ex, ipaddress.IPv6Network):
                            temp.update(al.address_exclude(ex))
                    except ValueError: pass
                else:
                    temp.add(al)
            final = temp
        return final

    def _collapse(self, networks: Iterable[NetworkObject], version: int) -> List[str]:
        # collapse_addresses requires a list of homogeneous types to be strictly safe
        if version == 4:
            v4_list = [n for n in networks if isinstance(n, ipaddress.IPv4Network)]
            return [str(net) for net in ipaddress.collapse_addresses(v4_list)]
        else:
            v6_list = [n for n in networks if isinstance(n, ipaddress.IPv6Network)]
            return [str(net) for net in ipaddress.collapse_addresses(v6_list)]