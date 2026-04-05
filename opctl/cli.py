import sys
from . import get_os_interface
from .adapters.json_repository import JsonPolicyRepository
from .cli_parser import build_parser
from .shell import OpctlShell

# Import Use Cases
from .use_cases.bulk_configure_uc import BulkConfigureUseCase
from .use_cases.status_report_uc import StatusReportUseCase
from .use_cases.commit_policy_uc import CommitPolicyUseCase
from .use_cases.transfer_config_uc import ImportConfigUseCase, ExportConfigUseCase
from .use_cases.list_interfaces_uc import ListInterfacesUseCase

def run_pipeline(args, repo, os_adapter):
    """Executes the single-line command pipeline."""
    
    if args.list_interfaces:
        res = ListInterfacesUseCase(repo, os_adapter).execute()
        print("\n--- OS Interfaces ---")
        for i in res["interfaces"]:
            print(f"[*] {i['name']} | MAC: {i['mac']} | IP: {i['ip']}")
        sys.exit(0)

    if args.import_file:
        ImportConfigUseCase(repo).execute(args.import_file)
        print(f"[*] Imported {args.import_file}.")

    # Stage Configuration
    if any([args.hostname, args.interface, args.unmanaged, args.targets, args.trusted, args.excludes]):
        if any([args.mode, args.ips, args.mac, args.ignore_dhcp_dns]) and not args.interface:
            print("\n[!] ERROR: -i required for interface settings.")
            sys.exit(1)

        config_kwargs = {
            "system": {"hostname": args.hostname, "unmanaged_interfaces": args.unmanaged},
            "interface_name": args.interface,
            "interface_config": {
                "mode": args.mode, "ip_addresses": args.ips, 
                "mac_address": args.mac, "dhcp_ignore_dns": args.ignore_dhcp_dns
            } if args.interface else None,
            "targets": args.targets if args.targets else None,
            "trusted": args.trusted if args.trusted else None,
            "excludes": args.excludes if args.excludes else None,
        }
        # Clean None values before sending to Use Case
        config_kwargs = {k: v for k, v in config_kwargs.items() if v is not None}
        BulkConfigureUseCase(repo).execute(config_kwargs)

    if args.status:
        for line in StatusReportUseCase(repo, os_adapter, os_adapter).execute():
            print(line)

    if args.commit:
        print("[*] Engaging Radio Silence...")
        CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
        print("[+] Committed.")

    if args.export_file:
        ExportConfigUseCase(repo).execute(args.export_file)

def main():
    repo = JsonPolicyRepository("session.json") 
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    # THE TRAFFIC COP
    if len(sys.argv) == 1:
        # No flags passed? Enter the shell.
        try:
            OpctlShell(repo, os_adapter).cmdloop()
        except KeyboardInterrupt:
            print("\nExiting opctl.")
            sys.exit(0)
    else:
        # Flags passed? Run the pipeline.
        parser = build_parser()
        args = parser.parse_args()
        run_pipeline(args, repo, os_adapter)

if __name__ == "__main__":
    main()