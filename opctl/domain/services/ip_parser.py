import ipaddress
from typing import Set, Union, List
from opctl.domain.exceptions.network import InvalidNetworkFormatError

class IPv6Parser:
    """Strictly handles standard IPv6 validation to prevent memory exhaustion."""
    @staticmethod
    def parse(input_str: str) -> Set[ipaddress.IPv6Network]:
        if '*' in input_str or '-' in input_str:
            raise InvalidNetworkFormatError(
                input_str, "Splat (*) and Dash (-) notations are not supported for IPv6. Use standard CIDR."
            )
        try:
            return {ipaddress.IPv6Network(input_str, strict=False)}
        except ValueError as e:
            raise InvalidNetworkFormatError(input_str, str(e))


class IPv4Parser:
    """Handles advanced cyber DSL (Splats, Dashes, CIDR) for IPv4."""
    @staticmethod
    def parse(input_str: str) -> Set[ipaddress.IPv4Network]:
        try:
            if '/' in input_str:
                base, mask = input_str.split('/')
            else:
                base, mask = input_str, "32"

            expanded_bases = IPv4Parser._recursive_expand(base.split('.'))
            final_nets = set()
            
            for b in expanded_bases:
                final_nets.add(ipaddress.IPv4Network(f"{b}/{mask}", strict=False))

            if not final_nets:
                raise InvalidNetworkFormatError(input_str, "Resulted in an empty network set.")
                
            return final_nets
        except ValueError as e:
            raise InvalidNetworkFormatError(input_str, str(e))

    @staticmethod
    def _recursive_expand(octets: List[str]) -> List[str]:
        if not octets:
            return [""]

        current = octets[0]
        rest = IPv4Parser._recursive_expand(octets[1:])
        results = []

        if current == '*':
            values = [str(i) for i in range(256)]
        elif '-' in current:
            try:
                start, end = map(int, current.split('-'))
                if start > end or start < 0 or end > 255:
                    raise ValueError("Dash range must be between 0 and 255, and start <= end.")
                values = [str(i) for i in range(start, end + 1)]
            except ValueError:
                raise ValueError(f"Malformed dashed octet: {current}")
        else:
            values = [current]

        for v in values:
            for r in rest:
                results.append(f"{v}.{r}".strip('.'))

        return results


class IPParser:
    """
    The Domain Service Facade. 
    Routes input strings to the correct underlying parsing strategy.
    """
    @staticmethod
    def parse(input_str: str) -> Set[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        # Explicitly declare the mixed type to satisfy strict typing
        result: Set[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = set()
        
        if ':' in input_str:
            result.update(IPv6Parser.parse(input_str))
        else:
            result.update(IPv4Parser.parse(input_str))
            
        return result