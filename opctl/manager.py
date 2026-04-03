import json
import os
from . import get_os_interface
from .common.net_utils import NetUtils

class OpManager:
    def __init__(self, state_file="session.json"):
        self.state_file = state_file
        self.os = get_os_interface()
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"hostname": "", "interface": "", "trusted": [], "targets": [], "excluded": []}

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def commit(self):
        """The Idempotent Action: Flushes the 'opctl' group and applies fresh."""
        final_rules = NetUtils.get_final_policy(
            self.state["trusted"], 
            self.state["targets"], 
            self.state["excluded"]
        )
        
        # Identity logic from your original wrapper
        if self.state["hostname"]:
            self.os.set_hostname(self.state["hostname"])
            
        # Firewall Logic: Namespaced to avoid clobbering Docker/System rules
        self.os.apply_op_policy(self.state["interface"], final_rules)
        print(f"Policy committed: {len(final_rules)} optimized rules applied.")