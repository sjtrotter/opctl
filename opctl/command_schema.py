# opctl/command_schema.py

COMMAND_SCHEMA = {
    # === META & ACTION COMMANDS ===
    "execute": {
        "flags": ["-x", "--execute"],
        "action": "store_true",
        "help": "Apply all staged configurations to the OS hardware",
        "usage": "execute",
        "valid_modes": ["root", "system", "policy", "interface"]
    },
    "write": {
        "flags": ["-w", "--write"],
        "type": str,
        "nargs": "?", # Optional argument
        "help": "Save the current configuration (or export to a file)",
        "usage": "write [filename]",
        "example": "write backup.json",
        "valid_modes": ["root", "system", "policy", "interface"]
    },
    "show": {
        "flags": ["-s", "--show"],
        "choices": ["interfaces", "edits"],
        "help": "Show system and network state",
        "usage": "show <interfaces|edits>",
        "example": "show edits",
        "valid_modes": ["root", "system", "policy", "interface"]
    },
    
    # === NAVIGATION COMMANDS (Shell Only) ===
    "exit": {
        "flags": [], "no_cli": True,
        "help": "Exit current mode or shell",
        "usage": "exit",
        "valid_modes": ["root", "system", "policy", "interface"]
    },
    "system": {
        "flags": [], "no_cli": True,
        "help": "Enter global system config mode",
        "usage": "system",
        "valid_modes": ["root"]
    },
    "policy": {
        "flags": [], "no_cli": True,
        "help": "Enter global firewall policy mode",
        "usage": "policy",
        "valid_modes": ["root"]
    },
    "interface": {
        "flags": ["-i", "--interface"],
        "type": str,
        "help": "Enter interface config mode (Supports quotes for Windows)",
        "usage": 'interface <"name">',
        "example": 'interface "Ethernet 2"',
        "valid_modes": ["root"]
    },

    # === CONFIGURATION PARAMETERS ===
    "mode": {
        "flags": ["--mode"], "choices": ["dhcp", "static", "promisc"],
        "help": "Interface routing mode", "usage": "mode <dhcp|static|promisc>",
        "valid_modes": ["interface"]
    },
    "ip": {
        "flags": ["-I", "--ips"], "nargs": "+",
        "help": "Assign IP(s) (CIDR)", "usage": "ip <cidr> [cidr...]",
        "valid_modes": ["interface"]
    },
    "mac": {
        "flags": ["--mac"], "type": str,
        "help": "Interface MAC ('random' for OPSEC)", "usage": "mac <address|random>",
        "valid_modes": ["interface"]
    },
    "hostname": {
        "flags": ["-H", "--hostname"], "type": str,
        "help": "Set system hostname", "usage": "hostname <name>",
        "valid_modes": ["system"]
    },
    "targets": {
        "flags": ["-t", "--targets"], "nargs": "+",
        "help": "Add tactical targets", "usage": "targets <cidr> [cidr...]",
        "valid_modes": ["policy", "interface"]
    },
    "trusted": {
        "flags": ["-T", "--trusted"], "nargs": "+",
        "help": "Add trusted networks", "usage": "trusted <cidr> [cidr...]",
        "valid_modes": ["policy", "interface"]
    },
    "excludes": {
        "flags": ["-e", "--excludes"], "nargs": "+",
        "help": "Add globally excluded networks", "usage": "excludes <cidr> [cidr...]",
        "valid_modes": ["policy", "interface"]
    }
}