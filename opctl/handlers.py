from .use_cases.bulk_configure_uc import BulkConfigureUseCase
from .use_cases.commit_policy_uc import CommitPolicyUseCase
from .use_cases.status_report_uc import StatusReportUseCase
from .use_cases.list_interfaces_uc import ListInterfacesUseCase
from .use_cases.transfer_config_uc import ExportConfigUseCase

def handle_execute(repo, os_adapter, payload):
    print("[*] Engaging Radio Silence... Committing to hardware.")
    CommitPolicyUseCase(repo, os_adapter, os_adapter, os_adapter).execute()
    print("[+] Done.")

def handle_show(repo, os_adapter, payload):
    target = payload.get("value", "edits")
    mode = payload.get("_mode", "root")
    iface = payload.get("_interface", None)

    if target == "interfaces" and mode == "root":
        res = ListInterfacesUseCase(repo, os_adapter).execute()
        for i in res["interfaces"]:
            m = "[staged]" if i["is_staged"] else " "
            print(f"{m:<10} {i['name']:<15} MAC: {i['mac']} IP: {i['ip']}")
    else:
        # Pass the context to the reactive report generator
        for line in StatusReportUseCase(repo, os_adapter, os_adapter).execute(mode=mode, target_interface=iface):
            print(line)

def handle_write(repo, os_adapter, payload):
    target = payload.get("value") or "session.json"
    ExportConfigUseCase(repo).execute(target)
    print(f"[*] Configuration saved to {target}")

def handle_config(repo, os_adapter, payload):
    BulkConfigureUseCase(repo).execute(payload)