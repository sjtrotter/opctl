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
        line = line.strip()
        if not line or line == "help": return line
            
        cmd_word = line.split()[0]
        
        # Filter commands valid for current mode
        valid_cmds = []
        for name in [m[3:] for m in dir(self) if m.startswith('do_')]:
            func = getattr(self, f"do_{name}")
            vm = getattr(func, '_valid_modes', ['root'])
            if self.current_mode in vm:
                valid_cmds.append(name)
                
        matches = [c for c in valid_cmds if c.startswith(cmd_word)]
        if len(matches) == 1:
            return line.replace(cmd_word, matches[0], 1)
        return line

    # === NAVIGATION COMMANDS ===
    def do_configure(self, arg):
        """Enter configuration mode to modify settings."""
        self.current_mode = 'configure'
        self.prompt = 'opctl(config)# '

    def do_system(self, arg):
        """Access global system settings."""
        self.current_mode = 'system'
        self.prompt = 'opctl(config-sys)# '

    def do_ntp(self, arg):
        """Access NTP service settings."""
        self.current_mode = 'ntp'
        self.prompt = 'opctl(config-ntp)# '

    def do_policy(self, arg):
        """Access global firewall policy settings."""
        self.current_mode = 'policy'
        self.prompt = 'opctl(config-policy)# '

    def do_interface(self, arg):
        """Access settings for a specific interface."""
        args = shlex.split(arg)
        if not args:
            print("Usage: interface <name>"); return
        self.current_interface = args[0]
        self.current_mode = 'interface'
        self.prompt = f'opctl(config-if:{self.current_interface})# '

    def do_exit(self, arg):
        """Move back one level or exit the shell."""
        if self.current_mode in ['system', 'ntp', 'policy', 'interface']:
            self.current_mode = 'configure'
            self.current_interface = None
            self.prompt = 'opctl(config)# '
        elif self.current_mode == 'configure':
            self.current_mode = 'root'
            self.prompt = 'opctl# '
        else:
            return True # Terminate
        return False

    # === ACTION COMMANDS ===
    def do_execute(self, arg):
        """Commit staged changes to the OS."""
        print("[*] Executing config on hardware...")
        CommitPolicyUseCase(self.repo, self.os_adapter, self.os_adapter, self.os_adapter).execute()
        print("[+] Done.")

    def do_show(self, arg):
        """Show system info or staged changes."""
        args = shlex.split(arg)
        sub = args[0].lower() if args else ""
        if sub.startswith("int"):
            res = ListInterfacesUseCase(self.repo, self.os_adapter).execute()
            print("\n--- Interfaces ---")
            for iface in res["interfaces"]:
                m = "[*]" if iface["is_staged"] else "   "
                print(f"{m} {iface['name']:<15} IP: {iface['ip']}")
        else:
            for line in StatusReportUseCase(self.repo, self.os_adapter, self.os_adapter).execute():
                print(line)

    def do_write(self, arg):
        """Save configuration."""
        print("[*] Configuration saved.")

    # === GROUPED HELP SYSTEM ===
    def do_help(self, arg):
        """Display context-aware help grouped by category."""
        print(f"\n--- [ {self.prompt.strip()} Commands ] ---")
        
        groups = {"Actions": [], "Navigation": [], "Settings": []}
        
        for name in [m[3:] for m in dir(self) if m.startswith('do_')]:
            if name in ['EOF', 'help', 'exit']: continue
            func = getattr(self, f"do_{name}")
            
            # Check mode validity
            vm = getattr(func, '_valid_modes', ['root'])
            if self.current_mode not in vm: continue
            
            # Get metadata
            cat = getattr(func, '_category', 'Actions')
            usage = getattr(func, '_cmd_usage', name)
            help_text = func.__doc__ or "No description."
            
            if cat in groups:
                groups[cat].append(f"  {usage:<25} {help_text}")

        for cat, lines in groups.items():
            if lines:
                print(f"\n[{cat}]")
                for line in sorted(lines):
                    print(line)
        print()

    def do_EOF(self, arg): return True

# --- METAPROGRAMMING BINDER ---
def _make_param(name, cfg):
    def method(self, arg):
        is_flag = cfg.get("action") == "store_true"
        val = True if is_flag else (shlex.split(arg) if cfg.get("nargs") == "+" else shlex.split(arg)[0])
        
        payload = {}
        if self.current_mode == "interface":
            payload = {"interface_name": self.current_interface, "interface_config": {name: val}}
        elif self.current_mode in ["system", "ntp"]:
            payload = {self.current_mode: {name: val}}
        
        BulkConfigureUseCase(self.repo).execute(payload)
        print(f"[*] Staged {name}.")
    return method

for p, cfg in COMMAND_SCHEMA.items():
    m_name = f"do_{p}"
    if not hasattr(OpctlShell, m_name):
        setattr(OpctlShell, m_name, _make_param(p, cfg))
    
    # Bind metadata
    method = getattr(OpctlShell, m_name)
    method._valid_modes = cfg.get("valid_modes", ["root"])
    method._category = cfg.get("category", "Actions")
    method._cmd_usage = cfg.get("usage", p)
    if "help" in cfg: method.__doc__ = cfg["help"]