# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_parsers.py

# Run a single test by name
python -m pytest tests/test_policy.py::TestOpPolicy::test_exclusion

# Install in editable mode (so `opctl` CLI works from anywhere)
pip install -e .

# Run directly without installing
python opctl.py
```

No build step is needed — zero external dependencies, pure Python stdlib.

## Architecture

**opctl** is a tactical network configuration tool (hostname, MAC, IP, DNS, firewall, NTP) that stages changes to JSON and commits them to the OS on demand. It supports Windows (PowerShell) and Linux (iproute2/iptables).

### Layered structure

```
Domain (no deps)   →  Use Cases  →  CLI / Shell
                              ↘  OS Adapters (Windows/Linux)
                              ↘  JSON Repository (adapters/)
```

- **`opctl/domain/`** — Pure business logic. Models are dataclasses with `from_dict`/`to_dict`. `OpPolicy` is the firewall rule engine (zone-based: trusted/target/excluded) with subnet algebra (`ipaddress.address_exclude`, `collapse_addresses`). `IPParser` supports CIDR, splat (`192.168.*.10`), and dash-range (`192.168.0-5.10`) notation for IPv4 only; IPv6 is strict CIDR only.
- **`opctl/use_cases/`** — Orchestration layer. Each use case loads staged state from the repo, applies changes, and either saves back or drives an OS adapter. `CommitPolicyUseCase` is the one that touches hardware.
- **`opctl/infrastructure/`** — `WindowsBackend` and `LinuxBackend` implement the three adapter interfaces (`ISystemAdapter`, `INetworkAdapter`, `IFirewallAdapter`). Selected at startup via `opctl/__init__.py::get_os_interface()`.
- **`opctl/adapters/`** — `JsonPolicyRepository` is the only persistence implementation (reads/writes `session.json`).
- **`opctl/command_schema.py`** — Single source of truth for all commands: name, aliases, flags, handler reference, and valid shell modes. Both the POSIX parser (`cli_parser.py`) and the interactive shell (`shell.py`) are generated dynamically from this schema.

### Staged vs live paradigm

All mutations write to `session.json` (staged state). `execute` / `CommitPolicyUseCase` pushes staged state to hardware. `show edits` / `ViewStatusUseCase` diffs staged against live OS state and displays `[SYNC]` / `[DIFF]` per field.

### Interactive shell

`OpctlShell` (inherits `cmd.Cmd`) has a modal hierarchy: `root` → `configure` → `{system, ntp, policy, interface <name>}`. The prompt reflects the current mode (e.g., `opctl(config-if:eth0)#`). Commands are attached as `do_*` methods via `setattr()` at init time using the command schema.

### Firewall zone model

`OpPolicy` compiles three zones — **trusted** (allow), **target** (allow), **excluded** (deny, overrides the other two) — into collapsed CIDR sets separately for IPv4 and IPv6. Port-based overrides use `IP:PORT` format. The `compile()` method returns a nested dict keyed by `{zone: {family: [networks]}}`.
