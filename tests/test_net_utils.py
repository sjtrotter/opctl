import ipaddress
from opctl.common.net_utils import NetUtils

def run_test_suite():
    # 1. Define complex "Operator" inputs
    test_inputs = [
        "192.168.0.0/24",       # Standard CIDR
        "192.168.0-1.0/24",     # Dashed octet with CIDR
        "192.168.*.10-12",      # Splat with a small dashed range
        "192.168.5.*",          # Splat for an entire octet
        "192.168.6.12",         # One specific IP
        "192.169.*.0/24"        # Splat with CIDR
    ]
    
    # 2. Define specific exclusions (The "Management" or "Safety" IPs)
    exclusions = [
        "192.168.0.1",          # Gateway of first range
        "192.168.1.1",          # Gateway of second range
        "192.168.5.11"          # One specific IP inside the splat range
    ]

    print(f"--- OPCTL NET_UTILS TEST ---")
    
    # Expand All Allowed
    all_allowed_ips = set()
    for inp in test_inputs:
        expanded = NetUtils.expand_input(inp)
        print(f"[+] Expanded '{inp}': found {len(expanded)} host(s)")
        all_allowed_ips.update(expanded)

    # Expand Exclusions
    all_excluded_ips = set()
    for exc in exclusions:
        expanded_exc = NetUtils.expand_input(exc)
        all_excluded_ips.update(expanded_exc)
    
    # Apply "Comm" Logic (Subtraction)
    final_ips = all_allowed_ips - all_excluded_ips
    print(f"\n[!] Post-Exclusion: {len(final_ips)} total usable IPs remaining.")

    # 3. Summarize/Super-net the results
    # This is where ipaddress.collapse_addresses minimizes the firewall lines
    final_policy = [str(net) for net in ipaddress.collapse_addresses(final_ips)]

    print(f"\n--- FINAL CALCULATED POLICY (Shortened) ---")
    for rule in final_policy:
        print(f"ALLOW -> {rule}")

if __name__ == "__main__":
    run_test_suite()