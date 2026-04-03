import ipaddress

class NetUtils:
    @staticmethod
    def expand_input(input_str):
        if '/' in input_str:
            base, mask = input_str.split('/')
        else:
            base, mask = input_str, "32"

        # 1. Expand the string into its base network strings
        expanded_bases = NetUtils._recursive_expand(base.split('.'))
        
        final_networks = []
        for b in expanded_bases:
            # Create a Network object instead of Host objects immediately
            # This preserves the integrity of the CIDR block
            net = ipaddress.IPv4Network(f"{b}/{mask}", strict=False)
            final_networks.append(net)

        # 2. Return a set of all usable IPs across all generated networks
        final_ips = set()
        for net in final_networks:
            # We only use .hosts() here so we don't accidentally allow 
            # the wire-address or broadcast-address
            final_ips.update(net.hosts() if net.prefixlen < 32 else [net.network_address])
            
        return final_ips
    
    @staticmethod
    def _recursive_expand(octets):
        """Processes each octet for dashes or splats."""
        if not octets:
            return [""]

        current = octets[0]
        rest = NetUtils._recursive_expand(octets[1:])
        
        results = []
        # Handle Splat (*)
        if current == '*':
            values = [str(i) for i in range(256)]
        # Handle Dash (0-1)
        elif '-' in current:
            start, end = map(int, current.split('-'))
            values = [str(i) for i in range(start, end + 1)]
        else:
            values = [current]

        for v in values:
            for r in rest:
                results.append(f"{v}.{r}".strip('.'))
        return results