import argparse
import sys
from .command_schema import COMMAND_SCHEMA

def build_parser():
    # allow_abbrev=True only works for --flags. For positional subparsers,
    # we'll handle abbreviations in the main execution loop.
    parser = argparse.ArgumentParser(
        description="opctl: Tactical Network Configuration Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparser_registry = {
        "root": parser.add_subparsers(dest="root_cmd", metavar="{command}", help="Root Commands")
    }

    # Pass 1: Create all Navigation "Nodes"
    nav_cmds = [k for k, v in COMMAND_SCHEMA.items() if v.get("type") == "nav"]
    for cmd in nav_cmds:
        cfg = COMMAND_SCHEMA[cmd]
        parent_mode = cfg["valid_modes"][0]
        
        if parent_mode in subparser_registry:
            node_parser = subparser_registry[parent_mode].add_parser(cmd, help=cfg.get("help"))
            
            if cmd == "interface":
                node_parser.add_argument("iface_target", help="Target interface name (e.g. eth0)")
            
            # Use 'metavar' so sub-commands show up in -h output
            subparser_registry[cmd] = node_parser.add_subparsers(
                dest=f"{cmd}_cmd", 
                metavar="{setting}", 
                help=f"{cmd} sub-commands"
            )

    # Pass 2: Add Leaf Settings and Actions
    for cmd, cfg in COMMAND_SCHEMA.items():
        if cfg.get("type") == "nav":
            continue
            
        for mode in cfg.get("valid_modes", ["root"]):
            if mode in subparser_registry:
                leaf_parser = subparser_registry[mode].add_parser(cmd, help=cfg.get("help"))
                
                arg_keys = ["nargs", "action", "choices", "default", "type", "metavar"]
                clean_cfg = {k: v for k, v in cfg.items() if k in arg_keys}
                
                # IMPORTANT: If the command is 'show', we need its arguments
                if cmd == "show":
                    leaf_parser.add_argument("value", nargs="?", default="edits", choices=["interfaces", "edits"])
                elif cfg.get("type") == "setting" and "action" not in clean_cfg:
                    leaf_parser.add_argument("value", **clean_cfg)
                elif clean_cfg:
                    leaf_parser.add_argument("value", **clean_cfg)

    return parser