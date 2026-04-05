import argparse
import sys

from . import get_os_interface
from .adapters.json_repository import JsonPolicyRepository
from .use_cases import (
    StatusReportUseCase, 
    CommitPolicyUseCase, 
    BulkConfigureUseCase,
    ImportConfigUseCase,
    ExportConfigUseCase,
    RemoveRuleUseCase,
    ListInterfacesUseCase
)

def main():
    # allow_abbrev=True is default in Python 3.5+, allowing --int to match --interface
    parser = argparse.ArgumentParser(
        prog="opctl", 
        description="OPerations ConTroLler (OPCTL) - A CLI tool for staging and committing network configurations with OPSEC in mind.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Information & Execution Flags ---
    parser.add_argument("-s", "--status", action="store_true", help="Print the configuration and live state")
    parser.add_argument("-c", "--commit", action="store_true", help="Apply the configuration to hardware")
    parser.add_argument("-l", "--list-interfaces", action="store_true", help="List available OS interfaces")
    
    # --- System & Networking Configuration ---
    parser.add_argument("-H", "--hostname", type=str, help="Stage the system hostname")
    parser.add_argument("-i", "--interface", type=str, help="Stage the target interface (e.g., eth0)")
    parser.add_argument("--mode", choices=["dhcp", "static"], help="Interface routing mode")
    parser.add_argument("--mac", type=str, help="Interface MAC address (use 'random' for OPSEC)")
    
    # --- Firewall Configuration (Using append to allow multiple flags) ---
    parser.add_argument("-t", "--targets", nargs='+', default=[], help="Stage tactical target networks")
    parser.add_argument("-T", "--trusted", nargs='+', default=[], help="Stage globally trusted networks")
    parser.add_argument("-e", "--excludes", nargs='+', default=[], help="Stage globally excluded networks")
    
    # --- Modifiers ---
    parser.add_argument("--add-target", nargs='+', default=[], help="Add to existing targets")
    parser.add_argument("--rm-target", nargs='+', default=[], help="Remove from existing targets")
    parser.add_argument("--add-trusted", nargs='+', default=[], help="Add to existing trusted")
    parser.add_argument("--rm-trusted", nargs='+', default=[], help="Remove from existing trusted")
    parser.add_argument("--add-exclude", nargs='+', default=[], help="Add to existing excludes")
    parser.add_argument("--rm-exclude", nargs='+', default=[], help="Remove from existing excludes")

    # --- File Operations ---
    parser.add_argument("--import-file", type=str, help="Import a session.json configuration")
    parser.add_argument("--export-file", type=str, help="Export current state to a file")

    args = parser.parse_args()
    
    # Dependency Injection
    repo = JsonPolicyRepository("session.json") 
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    # ---------------------------------------------------------
    # THE EXECUTION PIPELINE
    # This guarantees operations happen in a safe, logical order
    # regardless of what order the user typed the flags.
    # ---------------------------------------------------------
    try:
        # STEP 1: Info requests that exit early
        if args.list_interfaces:
            res = ListInterfacesUseCase(repo, os_adapter).execute()
            print("\n--- Available OS Network Interfaces ---")
            for iface in res["interfaces"]:
                m = "[*]" if iface["is_staged"] else "   "
                print(f"{m} {iface['name']} | MAC: {iface['mac']} | IP: {iface['ip']}")
            sys.exit(0)

        # STEP 2: File Imports
        if args.import_file:
            ImportConfigUseCase(repo).execute(args.import_file)
            print(f"[*] Imported {args.import_file}.")

        # STEP 3: State Modifications (Configure, Add, Remove)
        # We group all configuration arguments into a dictionary, filtering out Nones
        config_kwargs = {
            "hostname": args.hostname,
            "interface": args.interface,
            "mode": args.mode,
            "mac": args.mac,
            "targets": args.targets if args.targets else None,
            "trusted": args.trusted if args.trusted else None,
            "excludes": args.excludes if args.excludes else None,
        }
        config_kwargs = {k: v for k, v in config_kwargs.items() if v is not None}
        
        if config_kwargs:
            BulkConfigureUseCase(repo).execute(config_kwargs)
            print("[*] Configuration updated in session.")

        if args.add_target:
            BulkConfigureUseCase(repo).execute({"targets": args.add_target})
            print(f"[*] Added {len(args.add_target)} to targets.")
            
        if args.rm_target:
            RemoveRuleUseCase(repo).execute("target", args.rm_target)
            print(f"[*] Removed {len(args.rm_target)} from targets.")

        if args.add_trusted:
            BulkConfigureUseCase(repo).execute({"trusted": args.add_trusted})
            print(f"[*] Added {len(args.add_trusted)} to trusted.")
            
        if args.rm_trusted:
            RemoveRuleUseCase(repo).execute("trusted", args.rm_trusted)
            print(f"[*] Removed {len(args.rm_trusted)} from trusted.")

        if args.add_exclude:
            BulkConfigureUseCase(repo).execute({"excludes": args.add_exclude})
            print(f"[*] Added {len(args.add_exclude)} to excludes.")
            
        if args.rm_exclude:
            RemoveRuleUseCase(repo).execute("excludes", args.rm_exclude)
            print(f"[*] Removed {len(args.rm_exclude)} from excludes.")

        # STEP 4: Reporting
        if args.status:
            report_lines = StatusReportUseCase(repo, os_adapter, os_adapter).execute()
            for line in report_lines:
                print(line)

        # STEP 5: Execution (The "Send it" phase)
        if args.commit:
            print("[*] Engaging Radio Silence and committing config...")
            CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
            print("[+] Policy successfully committed.")

        # STEP 6: File Exports
        if args.export_file:
            ExportConfigUseCase(repo).execute(args.export_file)
            print(f"[+] Exported state to {args.export_file}.")

    except Exception as e:
        print(f"\n[!] ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()