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

def main() -> None:
    parser = argparse.ArgumentParser(prog="opctl", description="Tactical Workstation Bootstrapper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status / commit / list
    subparsers.add_parser("status", help="Preview configuration diff")
    subparsers.add_parser("commit", help="Execute Radio Silence flow")
    subparsers.add_parser("list-interfaces", help="List available OS interfaces")

    # add / rm
    p_add = subparsers.add_parser("add")
    p_add.add_argument("bucket", choices=["target", "trusted", "exclude"])
    p_add.add_argument("networks", nargs='+')

    p_rm = subparsers.add_parser("rm")
    p_rm.add_argument("bucket", choices=["target", "trusted", "exclude"])
    p_rm.add_argument("networks", nargs='+')

    # configure
    p_conf = subparsers.add_parser("configure")
    p_conf.add_argument("-H", "--hostname")
    p_conf.add_argument("-m", "--mac")
    p_conf.add_argument("-i", "--interface")
    p_conf.add_argument("--mode", choices=["dhcp", "static"], default="dhcp")
    p_conf.add_argument("-t", "--targets", nargs='+')
    p_conf.add_argument("-T", "--trusted", nargs='+')
    p_conf.add_argument("-e", "--excludes", nargs='+')
    p_conf.add_argument("-c", "--commit", action="store_true")

    # import / export
    p_imp = subparsers.add_parser("import")
    p_imp.add_argument("file")
    p_imp.add_argument("-c", "--commit", action="store_true")

    p_exp = subparsers.add_parser("export")
    p_exp.add_argument("file")

    args = parser.parse_args()
    repo = JsonPolicyRepository("session.json") 
    
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    try:
        if args.command == "status":
            # The Use Case now handles all formatting. CLI just prints.
            report_lines = StatusReportUseCase(repo, os_adapter, os_adapter).execute()
            for line in report_lines:
                print(line)
            
        elif args.command == "commit":
            CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
            print("[+] Policy successfully committed.")

        elif args.command == "list-interfaces":
            res = ListInterfacesUseCase(repo, os_adapter).execute()
            print("\n--- Available OS Network Interfaces ---")
            for iface in res["interfaces"]:
                m = "[*]" if iface["is_staged"] else "   "
                print(f"{m} {iface['name']} | MAC: {iface['mac']} | IP: {iface['ip']}")

        elif args.command == "add":
            kwargs = {f"{args.bucket}s": args.networks} 
            BulkConfigureUseCase(repo).execute(kwargs)
            print(f"[+] Added rules to {args.bucket}.")

        elif args.command == "rm":
            RemoveRuleUseCase(repo).execute(args.bucket, args.networks)
            print(f"[-] Removed rules from {args.bucket}.")

        elif args.command == "configure":
            BulkConfigureUseCase(repo).execute(vars(args))
            print("[+] Configuration staged.")
            if args.commit:
                CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
                print("[+] Policy committed.")

        elif args.command == "import":
            ImportConfigUseCase(repo).execute(args.file)
            print(f"[+] Imported {args.file}.")
            if args.commit:
                CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
                print("[+] Policy committed.")

        elif args.command == "export":
            ExportConfigUseCase(repo).execute(args.file)
            print(f"[+] Exported current config to {args.file}.")

    except Exception as e:
        # This is where your error was caught, likely because the CLI 
        # was trying to treat 'report_lines' (a list) as a dict.
        print(f"\n[!] ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()