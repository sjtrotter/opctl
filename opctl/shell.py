import cmd
import shlex
import sys
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

        self.alias_map = {}
        for canonical, cfg in COMMAND_SCHEMA.items():
            self.alias_map[canonical] = canonical
            for alias in cfg.get("aliases", []):
                self.alias_map[alias] = canonical

    def precmd(self, line: str) -> str:
        line = line.strip()
        if not line: return line
            
        parts = line.split()
        cmd_word = parts[0]
        
        if cmd_word in self.alias_map:
            parts[0] = self.alias_map[cmd_word]
            cmd_word = parts[0]

        valid_cmds = [name for name, cfg in COMMAND_SCHEMA.items() if self.current_mode in cfg.get("valid_modes", [])]
        matches = [c for c in valid_cmds if c.startswith(cmd_word)]
        
        if len(matches) == 1:
            parts[0] = matches[0]
            return " ".join(parts)
            
        return " ".join(parts)

    def default(self, line: str):
        cmd_word = line.split()[0]
        print(f"[!] Unknown or ambiguous command: {cmd_word}")

    def _dispatch_builtin(self, cmd_name, arg):
        if cmd_name == "help":
            self._print_help()
        elif cmd_name == "exit":
            if self.current_mode in ['system', 'ntp', 'policy', 'interface']:
                self.current_mode = 'configure'
                self.current_interface = None
                self.prompt = 'opctl(config)# '
            elif self.current_mode == 'configure':
                self.current_mode = 'root'
                self.prompt = 'opctl# '
            else:
                sys.exit(0)
        elif cmd_name == "EOF":
            print()
            sys.exit(0)

    def _dispatch_nav(self, cmd_name, arg):
        self.current_mode = cmd_name
        if cmd_name == "configure":
            self.prompt = 'opctl(config)# '
        elif cmd_name == "interface":
            args = shlex.split(arg)
            if not args:
                print("Usage error: 'interface' requires a target name (e.g. eth0).")
                self.current_mode = 'configure'
                return
            self.current_interface = args[0]
            self.prompt = f'opctl(config-if:{self.current_interface})# '
        else:
            self.prompt = f'opctl(config-{cmd_name})# '

    def _print_help(self):
        print(f"\n--- [ {self.prompt.strip()} Commands ] ---")
        groups = {"Actions": [], "Navigation": [], "Settings": [], "Built-in": []}
        
        for name, cfg in COMMAND_SCHEMA.items():
            if self.current_mode not in cfg.get("valid_modes", []):
                continue
                
            cat = cfg.get("category", "Settings")
            aliases = f" ({','.join(cfg['aliases'])})" if "aliases" in cfg else ""
            usage = f"{name}{aliases}"
            
            if name == "interface": usage += " <name>"
            elif cfg.get("nargs") == "+": usage += " <val1> [val2...]"
            elif cfg.get("nargs") == 1: usage += " <value>"
            
            help_text = cfg.get("help", "")
            groups[cat].append(f"  {usage:<30} {help_text}")

        for cat, lines in groups.items():
            if lines:
                print(f"\n[{cat}]")
                for line in sorted(lines): print(line)
        print()

def _create_method(cmd_name, cfg):
    """Creates a do_<cmd> method that routes to the schema handler."""
    def method(self, arg):
        if self.current_mode not in cfg.get("valid_modes", []):
            print(f"[!] Command '{cmd_name}' is not valid in [{self.current_mode}] mode.")
            return

        cmd_type = cfg.get("type")
        if cmd_type == "builtin": 
            self._dispatch_builtin(cmd_name, arg)
            return
        elif cmd_type == "nav": 
            self._dispatch_nav(cmd_name, arg)
            return

        handler = cfg.get("handler")
        if not handler:
            print(f"[!] Error: No handler defined for {cmd_name}")
            return

        args = shlex.split(arg)
        # Inject Context so the handler knows where we are!
        payload = {"_mode": self.current_mode, "_interface": self.current_interface}

        if cmd_type == "action":
            payload["value"] = args[0] if args else cfg.get("default")
            handler(self.repo, self.os_adapter, payload)
            
        elif cmd_type == "setting":
            is_flag = cfg.get("action") == "store_true"
            if is_flag: val = True
            else:
                if not args:
                    print(f"Usage error: '{cmd_name}' requires a value.")
                    return
                val = args if cfg.get("nargs") == "+" else args[0]
                choices = cfg.get("choices")
                if choices and (val not in choices and (isinstance(val, list) and not all(v in choices for v in val))):
                    print(f"Invalid choice. Valid options: {choices}")
                    return
            
            if self.current_mode == "interface":
                payload["interface_name"] = self.current_interface
                payload["interface_config"] = {cmd_name: val}
            elif self.current_mode in ["system", "ntp", "policy"]:
                payload[self.current_mode] = {cmd_name: val}
                
            handler(self.repo, self.os_adapter, payload)
            print(f"[*] Staged {cmd_name}.")
            
    method.__doc__ = cfg.get("help", "")
    return method

for name, config in COMMAND_SCHEMA.items():
    setattr(OpctlShell, f"do_{name}", _create_method(name, config))