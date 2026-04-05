import cmd
import shlex
from .use_cases.bulk_configure_uc import BulkConfigureUseCase
from .use_cases.status_report_uc import StatusReportUseCase
from .use_cases.commit_policy_uc import CommitPolicyUseCase
from .use_cases.list_interfaces_uc import ListInterfacesUseCase
from .use_cases.transfer_config_uc import ExportConfigUseCase
from .command_schema import COMMAND_SCHEMA

class OpctlShell(cmd.Cmd):
    intro = "\nWelcome to opctl Tactical Shell.\nType 'help' to see available commands.\n"
    prompt = 'opctl# '
    
    def __init__(self, repo, os_adapter):
        super().__init__()
        self.repo = repo
        self.os_adapter = os_adapter
        self.current_mode = 'root'
        self.current_interface = None

    def precmd(self, line: str) -> str:
        """Intercepts commands before execution to expand abbreviations (e.g., 'int' -> 'interface')."""
        line = line.strip()
        if not line:
            return line
            
        cmd_word = line.split()[0]
        
        # 1. Gather all valid commands for the CURRENT active menu
        valid_cmds = []
        for name in [m[3:] for m in dir(self) if m.startswith('do_')]:
            func = getattr(self, f"do_{name}")
            valid_modes = getattr(func, '_valid_modes', ['root', 'system', 'policy', 'interface'])
            if self.current_mode in valid_modes:
                valid_cmds.append(name)
                
        # 2. Find any commands that start with what the user typed
        matches = [c for c in valid_cmds if c.startswith(cmd_word)]
        
        if len(matches) == 1:
            # We found exactly one match! Rewrite the line and pass it down.
            expanded_cmd = matches[0]
            return line.replace(cmd_word, expanded_cmd, 1)
            
        # If 0 or >1 matches, let it fall through to default()
        return line

    def default(self, line: str) -> None:
        """Handles commands that failed to expand or execute."""
        cmd_word = line.split()[0]
        print(f"[!] Unknown or ambiguous command: {cmd_word}")
            
    # === META / ACTION COMMANDS ===
    def do_execute(self, arg):
        print("[*] Executing config on hardware...")
        CommitPolicyUseCase(self.repo, self.os_adapter, self.os_adapter, self.os_adapter).execute()
        print("[+] Hardware successfully configured.")

    def do_write(self, arg):
        try:
            args = shlex.split(arg)
        except ValueError:
            print("[!] Syntax error.") 
            return

        if args:
            # User typed `write backup.json`
            filename = args[0]
            ExportConfigUseCase(self.repo).execute(filename)
            print(f"[*] Configuration exported to {filename}")
        else:
            # Satisfy muscle memory for just typing `write`
            print("[*] Configuration securely saved to session.json")

    def do_show(self, arg):
        try:
            args = shlex.split(arg)
        except ValueError:
            print("[!] Syntax error.")
            return
            
        if not args:
            print("Usage: show <interfaces|edits>")
            return
            
        sub = args[0].lower()
        
        # 1. Programmatic Sub-Command Expansion!
        valid_choices = COMMAND_SCHEMA.get("show", {}).get("choices", ["interfaces", "edits"])
        
        try:
            sub = _resolve_abbreviation(sub, valid_choices)
        except ValueError as e:
            print(f"[!] {e}")
            return
            
        # 2. Execution
        if sub == "interfaces":
            res = ListInterfacesUseCase(self.repo, self.os_adapter).execute()
            print("\n--- Available OS Network Interfaces ---")
            for iface in res["interfaces"]:
                m = "[*]" if iface["is_staged"] else "   "
                print(f"{m} {iface['name']:<15} MAC: {iface['mac']} IP: {iface['ip']}")
            print()
            
        elif sub == "edits":
            for line in StatusReportUseCase(self.repo, self.os_adapter, self.os_adapter).execute():
                print(line)
        else:
            print(f"[!] Invalid show command: {sub}")

    # === NAVIGATION COMMANDS ===
    def do_system(self, arg):
        self.current_mode = 'system'
        self.prompt = 'opctl(config-sys)# '

    def do_policy(self, arg):
        self.current_mode = 'policy'
        self.prompt = 'opctl(config-policy)# '

    def do_interface(self, arg):
        try:
            args = shlex.split(arg)
        except ValueError:
            print("[!] Syntax error (check your quotes).")
            return
            
        if not args:
            print("Usage: interface <name>")
            return
            
        iface_name = args[0] # Properly extracts 'Ethernet 2' without quotes!
        self.current_mode = 'interface'
        self.current_interface = iface_name
        self.prompt = f'opctl(config-if:{iface_name})# '

    def do_exit(self, arg):
        if self.current_mode != 'root':
            self.current_mode = 'root'
            self.current_interface = None
            self.prompt = 'opctl# '
            return False
        return True

    # === MENU SYSTEM ===
    def do_help(self, arg):
        if arg:
            super().do_help(arg)
            return

        print(f"\n--- [ {self.prompt.strip(' #')} Commands ] ---")
        commands = [m for m in dir(self) if m.startswith('do_')]
        
        for cmd_name in sorted(commands):
            name = cmd_name[3:] 
            if name in ['EOF', 'help', 'question']: continue
                
            func = getattr(self, cmd_name)
            valid_modes = getattr(func, '_valid_modes', ['root', 'system', 'policy', 'interface'])
            if self.current_mode not in valid_modes: continue 
            
            usage = getattr(func, '_cmd_usage', name)
            example = getattr(func, '_cmd_example', '')
            doc = func.__doc__ or "No description available."
            
            print(f"  {usage:<30} {doc}")
            if example:
                print(f"  {'':<30} Example: {example}")
        print()
        
    def do_question(self, arg): 
        self.do_help(arg)

    def completenames(self, text, *ignored):
        names = super().completenames(text, *ignored)
        valid_names = []
        for name in names:
            func = getattr(self, f"do_{name}", None)
            if not func: continue
            valid_modes = getattr(func, '_valid_modes', ['root', 'system', 'policy', 'interface'])
            if self.current_mode in valid_modes:
                valid_names.append(name)
        return valid_names


# --- HELPER FUNCTIONS ---
def _resolve_abbreviation(typed_val: str, valid_choices: list) -> str:
    """Programmatically expands abbreviated sub-commands based on a list of choices."""
    matches = [c for c in valid_choices if c.startswith(typed_val.lower())]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise ValueError(f"Ambiguous argument '{typed_val}'. Matches: {', '.join(matches)}")
    return typed_val # Return as-is if no match, let downstream handle the error


# --- METAPROGRAMMING FACTORY ---
def _make_parameter_method(param_name, config_dict):
    """Generates the data-payload methods (like ip, mac, targets)"""
    def do_param(self, arg):
        try:
            args = shlex.split(arg) # Safe parsing for Windows!
        except ValueError:
            print("[!] Syntax error.")
            return
            
        if not args and config_dict.get("usage"):
            print(f"Usage: {config_dict.get('usage')}")
            return
            
        val = args if config_dict.get("nargs") == "+" else args[0]
        
        # --- NEW: Programmatic Schema-Driven Abbreviation ---
        choices = config_dict.get("choices")
        if choices and not isinstance(val, list):
            try:
                val = _resolve_abbreviation(val, choices)
            except ValueError as e:
                print(f"[!] {e}")
                return
        # ----------------------------------------------------
        
        if self.current_mode == "interface":
            payload = {"interface_name": self.current_interface, "interface_config": {param_name: val}}
            target_name = f"Interface {self.current_interface}"
        elif self.current_mode == "system":
            payload = {"system": {param_name: val}}
            target_name = "Global System"
        elif self.current_mode == "policy":
            payload = {param_name: val} 
            target_name = "Global Firewall Policy"
        else:
            return

        BulkConfigureUseCase(self.repo).execute(payload)
        print(f"[*] Staged {param_name} on {target_name}")

    return do_param

# --- THE UNIFIED BINDER ---
# We loop through the ONE schema. If a hardcoded method already exists (like do_write), 
# we just attach the schema's metadata to it! If it doesn't exist (like do_ip), we generate it.

for p, cfg in COMMAND_SCHEMA.items():
    method_name = f"do_{p}"
    
    # 1. Check if the method already exists in the class (e.g., do_show, do_write)
    if hasattr(OpctlShell, method_name):
        method = getattr(OpctlShell, method_name)
    else:
        # 2. If it doesn't exist, generate the parameter-setting method
        method = _make_parameter_method(p, cfg)
        setattr(OpctlShell, method_name, method)

    # 3. Bind the Schema metadata universally!
    method.__doc__ = cfg.get("help", "")
    method._valid_modes = cfg.get("valid_modes", []) # type: ignore
    method._cmd_usage = cfg.get("usage", p) # type: ignore
    method._cmd_example = cfg.get("example", "") # type: ignore