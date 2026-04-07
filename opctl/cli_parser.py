import argparse
from .command_schema import COMMAND_SCHEMA

def build_parser():
    parser = argparse.ArgumentParser(
        description="opctl: Tactical Network Configuration Utility (POSIX Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Operational mode or action")

    # 1. Build Action Parsers (e.g. 'show', 'write', 'execute')
    actions = {k: v for k, v in COMMAND_SCHEMA.items() if v.get("type") == "action"}
    for cmd, cfg in actions.items():
        act_parser = subparsers.add_parser(cmd, help=cfg.get("help"))
        if "choices" in cfg or "nargs" in cfg:
            act_parser.add_argument(
                "target", 
                nargs=cfg.get("nargs", "?"), 
                choices=cfg.get("choices"), 
                default=cfg.get("default"),
                help=f"Target for {cmd}"
            )

    # 2. Build Configuration Sub-Modes (e.g. 'system', 'interface')
    navs = {k: v for k, v in COMMAND_SCHEMA.items() if v.get("type") == "nav" and k != "configure"}
    for cmd, cfg in navs.items():
        # E.g., opctl interface <name> --ip 1.1.1.1
        nav_parser = subparsers.add_parser(cmd, help=cfg.get("help"), aliases=cfg.get("aliases", []))
        
        # Interfaces require a target positional
        if cmd == "interface":
            nav_parser.add_argument("iface_target", help="Target interface (e.g. eth0)")

        # Attach valid settings as POSIX flags for this specific mode
        valid_settings = {k: v for k, v in COMMAND_SCHEMA.items() if v.get("type") == "setting" and cmd in v.get("valid_modes", [])}
        
        for setting_name, setting_cfg in valid_settings.items():
            flags = setting_cfg.get("flags", [f"--{setting_name}"])
            
            # Filter argparse-compatible kwargs
            arg_keys = ["nargs", "action", "choices", "help"]
            kwargs = {k: v for k, v in setting_cfg.items() if k in arg_keys}
            
            # Use dest so it maps perfectly back to the schema's setting name
            nav_parser.add_argument(*flags, dest=setting_name, **kwargs)

    return parser