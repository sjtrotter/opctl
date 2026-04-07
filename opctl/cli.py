import sys
from typing import Dict, Any
from . import get_os_interface
from .adapters.json_repository import JsonPolicyRepository
from .cli_parser import build_parser
from .shell import OpctlShell
from .command_schema import COMMAND_SCHEMA

def resolve_posix_payload(args) -> Dict[str, Any]:
    """Translates POSIX flags into the standardized payload dictionary."""
    arg_dict = vars(args)
    raw_command = str(arg_dict.get("command", ""))
    
    if not raw_command:
        return {}

    # Normalize Aliases
    command = raw_command
    for cmd_name, cfg in COMMAND_SCHEMA.items():
        if raw_command == cmd_name or raw_command in cfg.get("aliases", []):
            command = cmd_name
            break

    settings_provided = {
        k: v for k, v in arg_dict.items() 
        if v is not None and k not in ["command", "iface_target", "target"]
    }
    
    # Notice we inject _mode so the 'show' handler works exactly like the Shell
    if command in ["execute", "write", "show"]:
        return {
            "value": arg_dict.get("target"),
            "_cmd_reference": command,
            "_mode": "root" 
        }

    if not settings_provided:
        print(f"[!] No configuration flags provided for {command}.")
        return {}

    payload: Dict[str, Any] = {"_cmd_reference": command}

    if command == "interface":
        payload["interface_name"] = str(arg_dict.get("iface_target", ""))
        payload["interface_config"] = settings_provided
    elif command in ["system", "ntp", "policy"]:
        payload[command] = settings_provided
        
    return payload

def main():
    repo = JsonPolicyRepository("session.json") 
    try:
        os_adapter = get_os_interface()
    except NotImplementedError as e:
        print(f"[!] OS Error: {e}")
        sys.exit(1)

    if len(sys.argv) == 1:
        try:
            OpctlShell(repo, os_adapter).cmdloop()
        except KeyboardInterrupt:
            print("\nExiting opctl.")
            sys.exit(0)
        return

    parser = build_parser()
    args = parser.parse_args()
    
    payload = resolve_posix_payload(args)
    if not payload:
        parser.print_help()
        sys.exit(1)

    cmd_ref = payload.pop("_cmd_reference", None)
    
    if cmd_ref and cmd_ref in COMMAND_SCHEMA:
        handler = COMMAND_SCHEMA[cmd_ref].get("handler")
        if handler:
            handler(repo, os_adapter, payload)
        else:
            fallback_handler = COMMAND_SCHEMA["hostname"].get("handler")
            if fallback_handler:
                fallback_handler(repo, os_adapter, payload)
                print(f"[*] Configuration staged successfully.")
            else:
                print("[!] Error: No valid handler found in schema.")
    else:
        print("[!] Error resolving command handler.")

if __name__ == "__main__":
    main()