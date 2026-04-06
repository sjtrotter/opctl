# The master list of all modes in the application
GLOBAL_COMMAND = ["root", "configure", "system", "ntp", "policy", "interface"]

COMMAND_SCHEMA = {
    # === GLOBAL ACTIONS ===
    "execute": {
        "category": "Actions",
        "help": "Commit staged configuration to hardware",
        "valid_modes": ["root"] 
    },
    "write": {
        "category": "Actions",
        "help": "Save current session to file",
        "usage": "write [filename]",
        "valid_modes": GLOBAL_COMMAND
    },
    "show": {
        "category": "Actions",
        "help": "Display live status or staged edits",
        "usage": "show <interfaces|edits>",
        "valid_modes": GLOBAL_COMMAND
    },

    # === NAVIGATION ===
    "configure": {
        "category": "Navigation",
        "help": "Enter configuration mode",
        "valid_modes": ["root"]
    },
    "system": {
        "category": "Navigation",
        "help": "Configure global system settings",
        "valid_modes": ["configure"]
    },
    "ntp": {
        "category": "Navigation",
        "help": "Configure NTP settings",
        "valid_modes": ["configure"]
    },
    "policy": {
        "category": "Navigation",
        "help": "Configure global firewall policy",
        "valid_modes": ["configure"]
    },
    "interface": {
        "category": "Navigation",
        "help": "Configure a specific network interface",
        "usage": "interface <name>",
        "valid_modes": ["configure"]
    },

    # === SETTINGS ===
    "hostname": {
        "category": "Settings",
        "help": "Set system hostname",
        "valid_modes": ["system"]
    },
    "dns": {
        "category": "Settings",
        "nargs": "+",
        "help": "Set DNS servers",
        "valid_modes": ["system", "interface"]
    },
    "servers": {
        "category": "Settings",
        "nargs": "+",
        "help": "Set NTP servers",
        "valid_modes": ["ntp"]
    },
    "ip": {
        "category": "Settings",
        "nargs": "+",
        "help": "Set static IP addresses",
        "valid_modes": ["interface"]
    },
    "enable": {
        "category": "Settings",
        "help": "Enable service or interface",
        "action": "store_true",
        "valid_modes": ["interface", "ntp"]
    },
    "disable": {
        "category": "Settings",
        "help": "Disable service or interface",
        "action": "store_true",
        "valid_modes": ["interface", "ntp"]
    }
}