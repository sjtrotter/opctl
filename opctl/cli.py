import sys
from . import get_os_interface
from .adapters.json_repository import JsonPolicyRepository
from .cli_parser import build_parser
from .shell import OpctlShell

# Use Cases
from .use_cases.bulk_configure_uc import BulkConfigureUseCase
from .use_cases.commit_policy_uc import CommitPolicyUseCase
from .use_cases.status_report_uc import StatusReportUseCase

def resolve_payload(args):
    """
    Translates nested argparse Namespace into a Use Case payload.
    Logic: Identify the deepest command in the chain and its context.
    """
    arg_dict = vars(args)
    payload = {}
    
    # 1. Determine the path taken through the subparsers
    # Chain will look like: ['configure', 'interface', 'ip']
    chain = [v for k, v in arg_dict.items() if k.endswith('_cmd') and v]
    if not chain:
        return None

    leaf_cmd = chain[-1]
    value = arg_dict.get("value")
    
    # 2. Identify the active mode (the command prior to the leaf)
    active_mode = chain[-2] if len(chain) > 1 else "root"

    # 3. Handle Special Direct Actions
    if leaf_cmd == "execute":
        return {"action": "execute"}
    if leaf_cmd == "show":
        return {"action": "show"}

    # 4. Map Configuration Settings to Payload
    if active_mode == "interface":
        payload = {
            "interface_name": arg_dict.get("iface_target"),
            "interface_config": {leaf_cmd: value}
        }
    elif active_mode in ["system", "ntp"]:
        payload = {active_mode: {leaf_cmd: value}}
    
    return payload

def resolve_abbreviations(args, schema):
    """
    Look at sys.argv and expand abbreviations based on the schema.
    ['conf', 'int', 'eth0'] -> ['configure', 'interface', 'eth0']
    """
    new_args = []
    for token in args:
        # Don't try to expand flags or interface names (which aren't in schema)
        if token.startswith('-') or token == "eth0": # Simplified check
            new_args.append(token)
            continue
            
        matches = [cmd for cmd in schema.keys() if cmd.startswith(token)]
        if len(matches) == 1:
            new_args.append(matches[0])
        else:
            new_args.append(token)
    return new_args

def main():
    repo = JsonPolicyRepository("session.json")
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    # NO ARGS -> SHELL MODE
    if len(sys.argv) == 1:
        try:
            OpctlShell(repo, os_adapter).cmdloop()
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)
        return

    # ARGS -> ONE-LINER MODE
    parser = build_parser()
    args = parser.parse_args()
    
    payload = resolve_payload(args)
    if not payload:
        parser.print_help()
        sys.exit(1)

    # EXECUTION
    if payload.get("action") == "execute":
        print("[*] Engaging Radio Silence... Committing to hardware.")
        CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
        print("[+] Done.")
        
    elif payload.get("action") == "show":
        for line in StatusReportUseCase(repo, os_adapter, os_adapter).execute():
            print(line)
            
    else:
        # Standard Configuration Staging
        BulkConfigureUseCase(repo).execute(payload)
        print(f"[*] Staged {payload}")

if __name__ == "__main__":
    main()