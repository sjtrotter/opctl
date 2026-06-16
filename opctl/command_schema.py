# Import Use Cases to bind them to the commands
from .use_cases.bulk_configure_uc import BulkConfigureUseCase
from .use_cases.commit_policy_uc import CommitPolicyUseCase
from .use_cases.status_report_uc import StatusReportUseCase
from .use_cases.list_interfaces_uc import ListInterfacesUseCase
from .use_cases.transfer_config_uc import ExportConfigUseCase

# The master list of valid operational modes
VALID_MODES = ["root", "configure", "system", "ntp", "policy", "interface"]

# --- Handler Callbacks ---
def handle_execute(repo, os_adapter, payload):
    print("[*] Engaging Radio Silence... Committing to hardware.")
    report = CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()

    marks = {"ok": "[ ok ]", "failed": "[FAIL]", "skipped": "[skip]"}
    for step in report.steps:
        line = f"  {marks.get(step.status, '[ ?? ]')} {step.name}"
        if step.detail:
            line += f"  ({step.detail})"
        print(line)

    if report.rolled_back:
        print("\n[!] Commit failed — rolling back to the pre-commit state:")
        for step in report.rollback_steps:
            mark = marks["ok"] if step.status == "ok" else marks["failed"]
            line = f"  {mark} {step.name}"
            if step.detail:
                line += f"  ({step.detail})"
            print(line)
        print("\n[!] System restored as closely as the OS layer allows. Review before retrying.")
    elif report.success:
        print("\n[+] Done. All steps applied.")
    else:
        print("\n[!] Commit incomplete.")

def handle_show(repo, os_adapter, payload):
    payload = payload or {}
    target = payload.get("value") or "edits"
    if target == "interfaces":
        res = ListInterfacesUseCase(repo, os_adapter).execute()
        print("\n--- Available OS Network Interfaces ---")
        for iface in res["interfaces"]:
            m = "[*]" if iface["is_staged"] else "   "
            print(f"{m} {iface['name']:<15} MAC: {iface['mac']} IP: {iface['ip']}")
    else:
        mode = payload.get("_mode", "root")
        target_interface = payload.get("_interface")
        for line in StatusReportUseCase(repo, os_adapter, os_adapter).execute(mode, target_interface):
            print(line)

def handle_write(repo, os_adapter, payload):
    payload = payload or {}
    target = payload.get("value") or "session.json"
    ExportConfigUseCase(repo).execute(target)
    print(f"[*] Configuration saved to {target}")

def handle_config(repo, os_adapter, payload):
    BulkConfigureUseCase(repo).execute(payload)
    payload = payload or {}
    # Name what was staged without leaking internal context keys (e.g. "_mode").
    if "interface_name" in payload:
        staged_item = payload["interface_name"]
    else:
        staged_item = next((k for k in payload if not k.startswith("_")), "settings")
    print(f"[*] Configuration staged for {staged_item}")

# --- Schema ---
COMMAND_SCHEMA = {
    # === SHELL BUILT-INS ===
    "help": {
        "type": "builtin",
        "category": "Built-in",
        "help": "Show this help menu",
        "aliases": ["?"],
        "valid_modes": VALID_MODES
    },
    "exit": {
        "type": "builtin",
        "category": "Built-in",
        "help": "Move back one level or exit the shell",
        "aliases": ["quit"],
        "valid_modes": VALID_MODES
    },
    "EOF": {
        "type": "builtin",
        "category": "Built-in",
        "help": "Handle Ctrl+D to exit safely",
        "valid_modes": VALID_MODES
    },

    # === GLOBAL ACTIONS ===
    "execute": {
        "type": "action",
        "category": "Actions",
        "help": "Commit staged configuration to hardware",
        "handler": handle_execute,
        "valid_modes": ["root"]
    },
    "write": {
        "type": "action",
        "category": "Actions",
        "help": "Save current session to file",
        "nargs": "?",
        "default": "session.json",
        "handler": handle_write,
        "valid_modes": VALID_MODES
    },
    "show": {
        "type": "action",
        "category": "Actions",
        "help": "Display live status or staged edits",
        "nargs": "?",
        "choices": ["interfaces", "edits"],
        "default": "edits",
        "handler": handle_show,
        "valid_modes": VALID_MODES
    },

    # === NAVIGATION ===
    "configure": {
        "type": "nav",
        "category": "Navigation",
        "help": "Enter configuration mode",
        "aliases": ["conf", "config"],
        "valid_modes": ["root"]
    },
    "system": {
        "type": "nav",
        "category": "Navigation",
        "help": "Configure global system settings",
        "aliases": ["sys"],
        "valid_modes": ["configure"]
    },
    "ntp": {
        "type": "nav",
        "category": "Navigation",
        "help": "Configure NTP settings",
        "valid_modes": ["configure"]
    },
    "policy": {
        "type": "nav",
        "category": "Navigation",
        "help": "Configure global firewall policy",
        "aliases": ["pol"],
        "valid_modes": ["configure"]
    },
    "interface": {
        "type": "nav",
        "category": "Navigation",
        "help": "Configure a specific network interface",
        "aliases": ["int"],
        "valid_modes": ["configure"]
    },

    # === SETTINGS ===
    # Notice all settings share the handle_config callback
    "hostname": {
        "type": "setting",
        "category": "Settings",
        "help": "Set system hostname",
        "flags": ["--hostname", "-n"],
        "handler": handle_config,
        "valid_modes": ["system"]
    },
    "unmanaged": {
        "type": "setting",
        "category": "Settings",
        "help": "Set the unmanaged interface policy",
        "choices": ["ignore", "isolate", "disable"],
        "flags": ["--unmanaged", "-u"],
        "handler": handle_config,
        "valid_modes": ["system"]
    },
    "dns": {
        "type": "setting",
        "category": "Settings",
        "nargs": "+",
        "help": "Set DNS servers",
        "flags": ["--dns", "-d"],
        "handler": handle_config,
        "valid_modes": ["system", "interface"]
    },
    "ip": {
        "type": "setting",
        "category": "Settings",
        "nargs": "+",
        "help": "Set static IP addresses",
        "flags": ["--ip", "-i"],
        "handler": handle_config,
        "valid_modes": ["interface"]
    },
    "mac": {
        "type": "setting",
        "category": "Settings",
        "help": "Set MAC address or 'random'",
        "flags": ["--mac", "-m"],
        "handler": handle_config,
        "valid_modes": ["interface"]
    },
    "mode": {
        "type": "setting",
        "category": "Settings",
        "choices": ["dhcp", "static"],
        "help": "Set interface mode (dhcp/static)",
        "flags": ["--mode"],
        "handler": handle_config,
        "valid_modes": ["interface"]
    },
    "enable": {
        "type": "setting",
        "category": "Settings",
        "help": "Enable service or interface",
        "action": "store_true",
        "flags": ["--enable", "-e"],
        "handler": handle_config,
        "valid_modes": ["interface", "ntp"]
    },
    "disable": {
        "type": "setting",
        "category": "Settings",
        "help": "Disable service or interface",
        "action": "store_true",
        "flags": ["--disable"],
        "handler": handle_config,
        "valid_modes": ["interface", "ntp"]
    },

    # === FIREWALL ZONE RULES ===
    # Valid in 'policy' (global) and 'interface' (per-NIC) modes. The command name
    # is the firewall zone; BulkConfigureUseCase appends each value to that zone.
    "trusted": {
        "type": "setting",
        "category": "Firewall",
        "nargs": "+",
        "help": "Add trusted (allow) networks/hosts: CIDR, IP, splat, range, or IP:PORT",
        "flags": ["--trusted", "-t"],
        "handler": handle_config,
        "valid_modes": ["policy", "interface"]
    },
    "target": {
        "type": "setting",
        "category": "Firewall",
        "nargs": "+",
        "help": "Add target (allow) networks/hosts: CIDR, IP, splat, range, or IP:PORT",
        "flags": ["--target"],
        "handler": handle_config,
        "valid_modes": ["policy", "interface"]
    },
    "excluded": {
        "type": "setting",
        "category": "Firewall",
        "nargs": "+",
        "help": "Add excluded (deny) networks/hosts: overrides trusted/target",
        "flags": ["--excluded", "-x"],
        "handler": handle_config,
        "valid_modes": ["policy", "interface"]
    }
}