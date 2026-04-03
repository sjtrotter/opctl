import argparse
import sys
import json

from . import get_os_interface
from .adapters.json_repository import JsonPolicyRepository
from .use_cases import (
    ViewStatusUseCase, 
    CommitPolicyUseCase, 
    BulkConfigureUseCase,
    ImportConfigUseCase,
    ExportConfigUseCase,
    RemoveRuleUseCase
)

def main():
    # --- TOP LEVEL PARSER ---
    parser = argparse.ArgumentParser(
        prog="opctl", 
        description="Tactical Workstation Bootstrapper - Provision and secure operational environments.",
        epilog="Run 'opctl <command> --help' for detailed information on a specific command.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- 1. CORE OPERATIONS ---
    subparsers.add_parser("status", help="Preview configuration and math before committing")
    subparsers.add_parser("commit", help="Execute the Radio Silence provisioning flow")

    # --- 2. MODULAR CONFIGURATION ---
    parser_id = subparsers.add_parser("set-identity", help="Stage hostname and MAC")
    parser_id.add_argument("--hostname", metavar="NAME", help="Desired hostname")
    parser_id.add_argument("--mac", metavar="MAC", help="Specific MAC or 'random'")

    parser_add = subparsers.add_parser("add", help="Add rules to a policy bucket")
    parser_add.add_argument("bucket", choices=["target", "trusted", "exclude"])
    parser_add.add_argument("networks", nargs='+', metavar="IP[:PORT][/CIDR]", help="One or more rules (e.g., 10.0.0.0/8, 192.168.1.50:443)")

    parser_rm = subparsers.add_parser("rm", help="Remove rules from a policy bucket")
    parser_rm.add_argument("bucket", choices=["target", "trusted", "exclude"])
    parser_rm.add_argument("networks", nargs='+', metavar="IP[:PORT][/CIDR]", help="One or more rules to explicitly remove")

    # --- 3. BULK CONFIGURATION (The God Command) ---
    parser_conf = subparsers.add_parser(
        "configure", 
        help="Define the entire configuration via flags",
        description="The God Command. Provision the entire operational workstation in a single line.",
        epilog="""
Examples:
  # Rapid tactical deployment with automatic commit
  opctl configure -H ghost-01 -m random -i eth0 -t 192.168.1.0/24 -c

  # Stage a complex setup: Broad block, but allow a specific port
  opctl configure -H jump-box -e 10.0.0.0/8 -t 10.1.2.3:80
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Argument Groups for clean UI
    id_group = parser_conf.add_argument_group("Identity Flags")
    id_group.add_argument("-H", "--hostname", metavar="NAME", help="Set Hostname")
    id_group.add_argument("-m", "--mac", metavar="MAC", help="Set MAC address or 'random'")

    net_group = parser_conf.add_argument_group("Network Flags")
    net_group.add_argument("-i", "--interface", metavar="IFACE", help="Set outbound interface (e.g., eth0)")
    net_group.add_argument("--mode", choices=["dhcp", "static"], default="dhcp", help="IP assignment mode (default: dhcp)")

    pol_group = parser_conf.add_argument_group("Policy/Firewall Flags")
    pol_group.add_argument("-t", "--targets", nargs='+', metavar="IP[:PORT][/CIDR]", help="Target networks or specific ports (Egress only)")
    pol_group.add_argument("-T", "--trusted", nargs='+', metavar="IP[:PORT][/CIDR]", help="Trusted networks or specific ports (Bi-directional)")
    pol_group.add_argument("-e", "--excludes", nargs='+', metavar="IP[:PORT][/CIDR]", help="Excluded networks or specific ports (Drop)")
    
    exec_group = parser_conf.add_argument_group("Execution Flags")
    exec_group.add_argument("-c", "--commit", action="store_true", help="Immediately commit after configuring")

    # --- 4. PLAYBOOK IMPORT/EXPORT ---
    parser_import = subparsers.add_parser("import", help="Load a JSON playbook")
    parser_import.add_argument("file", help="Path to the .json playbook")
    parser_import.add_argument("-c", "--commit", action="store_true", help="Immediately commit the loaded playbook")

    parser_export = subparsers.add_parser("export", help="Export current config to a JSON playbook")
    parser_export.add_argument("file", help="Destination path for the .json playbook")

    args = parser.parse_args()

    # --- DEPENDENCY INJECTION ---
    repo = JsonPolicyRepository("session.json") 
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    # --- ROUTING ---
    try:
        if args.command == "status":
            report = ViewStatusUseCase(repo, os_adapter, os_adapter).execute()
            print(json.dumps(report, indent=2))
            
        elif args.command == "commit":
            print("[*] Committing policy via Radio Silence flow...")
            CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
            print("[+] Policy successfully committed. Interface is hot.")

        elif args.command == "set-identity":
            BulkConfigureUseCase(repo).execute({"hostname": args.hostname, "mac": args.mac})
            print("[+] Identity staged.")

        elif args.command == "add":
            kwargs = {f"{args.bucket}s": args.networks} 
            BulkConfigureUseCase(repo).execute(kwargs)
            print(f"[+] Added {len(args.networks)} rule(s) to the '{args.bucket}' bucket.")

        elif args.command == "rm":
            RemoveRuleUseCase(repo).execute(args.bucket, args.networks)
            print(f"[-] Removed {len(args.networks)} rule(s) from the '{args.bucket}' bucket.")

        elif args.command == "configure":
            BulkConfigureUseCase(repo).execute(vars(args))
            print("[+] Configuration staged.")
            if args.commit:
                print("[*] Committing policy...")
                CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
                print("[+] Policy successfully committed. Interface is hot.")

        elif args.command == "import":
            ImportConfigUseCase(repo).execute(args.file)
            print(f"[+] Playbook '{args.file}' successfully imported and staged.")
            if args.commit:
                print("[*] Committing loaded playbook...")
                CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
                print("[+] Policy successfully committed. Interface is hot.")

        elif args.command == "export":
            ExportConfigUseCase(repo).execute(args.file)
            print(f"[+] Current session successfully exported to '{args.file}'.")

    except Exception as e:
        print(f"\n[!] ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()