# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests (the suite is pytest-based)
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_parsers.py

# Run a single test by name
python -m pytest tests/test_policy.py::TestOpPolicy::test_compile_with_exclusions

# Install in editable mode (exposes the `opctl` console script anywhere)
pip install -e .

# Run without installing (equivalent to the `opctl` entry point, opctl.cli:main)
python opctl.py
```

No build step is needed. The package itself has **zero third-party runtime dependencies** — pure
Python stdlib, `requires-python >= 3.8`. The **test suite requires `pytest`** (the only dev
dependency; it is not declared in `pyproject.toml`, so `pip install pytest` first if needed).

## Engineering principles

Hold every change to these standards. They are not aspirational — they are the bar for any code that
lands here.

- **Clean code.** Small, single-responsibility units; intention-revealing names; no dead code,
  duplication, or commented-out blocks. Match the style, naming, and comment density of the
  surrounding code. Add a behavior-covering test with every change. Leave each file clearer than you
  found it.
- **Domain-driven, layered architecture.** Respect the dependency rule — `opctl/domain/` imports
  nothing from outer layers; use cases orchestrate; `infrastructure/` and `adapters/` depend inward,
  never the reverse. Business rules live in the domain (models, services), **not** in handlers, the
  shell, the CLI, or providers. Cross layer boundaries only through the ABC ports in
  `domain/interfaces.py`, and keep all I/O, `subprocess`, and OS specifics inside
  `infrastructure/` / `adapters/`.
- **Python best practices.** PEP 8, type hints on public signatures, dataclasses for value objects,
  stdlib (`ipaddress`, `pathlib`, `subprocess` list-form, …) over hand-rolled equivalents, explicit
  exceptions over silent failure, and context managers for resources. Preserve the
  **zero-runtime-dependency** rule (stdlib only).
- **Deviations require prior developer approval and a written note.** If a task appears to need
  breaking any principle above — logic in an adapter, a new runtime dependency, a layering shortcut,
  an untested change — **stop and get the developer's sign-off first.** Once approved, record the
  deviation at the call site (`# DEVIATION: <what> — <why> — approved by <who>, <date>`) and, when it
  is architecturally notable, add a line to **Conventions & gotchas** below. Never deviate silently.

## Architecture

**opctl** is a cross-platform (Linux + Windows) tactical network configurator — hostname, per-NIC
MAC address, IPv4/IPv6 addressing (static or DHCP), DNS, a zone-based egress firewall, and NTP. It
**stages** changes to a JSON file and **commits** them to the OS on demand. Two front-ends drive the
same core: a one-shot POSIX CLI (`opctl <cmd> --flags`) and an interactive, Cisco-IOS-style modal
shell (bare `opctl`).

### Layered / hexagonal structure

```
Front-ends:  POSIX CLI (cli.py + cli_parser.py)  ─┐
             Interactive shell (shell.py)         ─┤  both generated from command_schema.py
                                                   ▼
             Use Cases (use_cases/)  ── orchestration: load staged state → mutate → save,
                                        OR drive the OS backend
                          ├─→ JSON Repository (adapters/json_repository.py ↔ session.json)
                          └─→ OS Backend (infrastructure/) ─→ resolved Providers ─→ OS CLI tools

             Domain (domain/) — pure, no outward deps: models, IPParser, ABC ports, exceptions
```

- **`opctl/domain/`** — Pure business logic, no imports from outer layers.
  - `models/` — `OpProfile` is the **aggregate root** (a plain class) and owns all JSON
    (de)serialization. It bundles `SystemProfile`, `NetworkProfile`, `NtpProfile`,
    `Dict[str, InterfaceProfile]`, a global `OpPolicy`, a `BackendConfig`, and an optional
    `MissionMeta` (`meta`, serialized only when present). **Only
    `InterfaceProfile` is a dataclass with `from_dict`**; the leaf profiles are dataclasses with
    `to_dict` only, and `OpProfile.from_dict` rebuilds them inline with `dict.get()` defaults (so
    adding a leaf-profile field means editing two places). `OpProfile`/`OpPolicy` are plain classes,
    not dataclasses.
  - `services/ip_parser.py` — `IPParser` routes by `:` to `IPv6Parser` / `IPv4Parser`. IPv4 supports
    CIDR, splat (`192.168.*.10`), and inclusive dash-range (`192.168.0-5.10`); a bare address becomes
    `/32`. **IPv6 is strict CIDR only** (splat/dash raise, to prevent memory exhaustion). Callers
    must strip any `:PORT` before parsing, since a colon forces the IPv6 path.
  - `interfaces.py` — **five** ABC ports: the three adapter ports (`ISystemAdapter`,
    `INetworkAdapter`, `IFirewallAdapter`), plus `IProvider` (`provider_name()` / `is_available()`,
    used for selection) and `IPolicyRepository`.
  - `exceptions/` — `OpCtlDomainError` root, `InvalidNetworkFormatError`, `ConflictingPolicyError`.
- **`opctl/use_cases/`** — Orchestration. Each loads staged state, applies changes, and either saves
  back or drives an OS adapter. `CommitPolicyUseCase` is the **only** one that touches hardware.
- **`opctl/infrastructure/`** — `LinuxBackend` / `WindowsBackend` are thin **facades** that hold no
  logic; each resolves three **providers** (system / network / firewall) and forwards every adapter
  method 1:1. Selected at startup via `opctl/__init__.py::get_os_interface()`. See the provider layer
  below.
- **`opctl/adapters/`** — `JsonPolicyRepository` is the only persistence implementation. It is
  schema-agnostic (returns the raw dict; `{}` for both a missing and a corrupted file) and resolves
  `session.json` **relative to the current working directory**. The on-disk schema is owned by
  `OpProfile.to_dict()`, not the repository.
- **`opctl/command_schema.py`** — **Single source of truth** for all commands: name, aliases, flags,
  `valid_modes`, handler reference, and command type. Both the POSIX parser (`cli_parser.py`) and the
  interactive shell (`shell.py`) are generated dynamically from this schema. **Add commands/flags
  here, not in the parser or shell.**

### Provider layer (per-OS, auto-resolved)

The backends do not implement OS logic themselves — they compose **providers**, one per concern,
each wrapping a specific OS CLI tool. `BackendConfig` (three fields, each defaulting to `"auto"`,
read from `session.json`'s top-level `backend` block, and staged via the `backend` command —
`configure` → `backend`, or `opctl backend --firewall-provider …`) drives selection via
`infrastructure/_resolve.py::resolve_provider`:

- `"auto"` → the **first** candidate whose `is_available()` (a `shutil.which()` PATH check) is true;
  none available → `RuntimeError`.
- explicit name → the candidate whose `provider_name()` matches; no match → `ValueError`.

**Candidate-list order = precedence.** All providers extend a shared base
(`linux/providers/_base.py::LinuxProvider`, `windows/providers/_base.py::WindowsProvider`) that
supplies the subprocess runner and re-exports the central validators.

| Concern | Linux (in precedence order) | Windows (in precedence order) |
|---|---|---|
| **system** (hostname) | `hostnamectl` → `hostname` | `powershell` (`Rename-Computer`) → `wmic` |
| **network** (NIC/L3) | `nmcli` → `iproute2` (`ip`) → `ifconfig` | `powershell` (`Net*` cmdlets) → `netsh` |
| **firewall** | `firewalld` → `ufw` → `iptables` | `powershell` (`New-NetFirewallRule`) → `netsh` |

PowerShell is first on Windows, so it is the default whenever `powershell` is on PATH.

### Staged vs live paradigm

All mutations write to `session.json` (staged intent). Nothing touches hardware as you type.
`show` (→ `StatusReportUseCase` → `ViewStatusUseCase`) diffs staged against live OS state and renders
a **diff-first** report — a tally line, then `CHANGES` (`live -> staged`), `IN SYNC`, and `STAGED`
(fields with no live equivalent) groups; unconfigured fields are omitted. Only `execute`
(→ `CommitPolicyUseCase`) pushes the staged profile to the OS, as a tracked transaction with
best-effort rollback. Commit order: set hostname → flush managed firewall rules → apply global policy
(blocks, then allows) → per-interface loop (down → MAC → local policy → static/DHCP → up; disabled
interfaces are just brought down and skipped) → **unmanaged-interface policy** (`isolate` = deny-all
egress, `disable` = link down, for NICs present on the host but not in the session; `ignore` = no-op).

### Interactive shell

`OpctlShell` (inherits `cmd.Cmd`) has a modal hierarchy: `root` → `configure` →
`{system, ntp, policy, interface <name>}`. The prompt reflects the mode (`opctl# `,
`opctl(config)# `, `opctl(config-system)# `, `opctl(config-if:eth0)# `). `exit`/`quit` moves up one
level; at root, `exit`/Ctrl+D quits. Commands are attached as `do_*` methods via `setattr()` at
import time from the command schema — the class body defines none. `precmd` resolves aliases and does
unique-prefix abbreviation within the current mode.

### Firewall zone model

`OpPolicy` compiles three zones — **trusted** (allow), **target** (allow), **excluded** (deny,
overrides the other two) — into collapsed CIDR sets, separately for IPv4 and IPv6. Excluded networks
are subtracted from trusted/target via `ipaddress.address_exclude` + `collapse_addresses`. Port
overrides use `IP:PORT` (IPv4) / `[IPv6]:PORT` form. `compile(parse_strategy)` takes the IP parser as
a **strategy argument** (keeping the domain dependency-free — pass `IPParser.parse`) and returns:

```python
{ "v4": {"trusted": [...], "targets": [...], "blocked": [...],
         "port_blocks": [...], "port_allows": [...]},
  "v6": { ... same keys ... } }
```

Note the shape: the **outer** key is the family (`"v4"`/`"v6"`); the inner keys are
`trusted`/`targets`/`blocked`/`port_blocks`/`port_allows`.

## Conventions & gotchas

- **`command_schema.py` is the SSOT.** The two front-ends both generate from it. `len(sys.argv) == 1`
  launches the shell; any argument uses the POSIX path.
- **POSIX dispatch quirk:** `nav` commands (`system`, `ntp`, `policy`, `interface`) carry **no**
  `handler`, so for them `cli.main()` falls back to `COMMAND_SCHEMA["hostname"]["handler"]` (which is
  `handle_config`) at `cli.py:90`. This fallback branch is load-bearing, not dead. `execute` /
  `write` / `show` (type `action`) have their own handlers.
- **The live handlers are inline at the top of `command_schema.py`** (`handle_execute` /
  `handle_show` / `handle_write` / `handle_config`) — edit those.
- **Firewall rule commands** (`trusted` / `target` / `excluded`, valid in `policy` and `interface`
  modes) stage via `handle_config` → `BulkConfigureUseCase._stage_rules`, which **appends** each value
  to the named zone. Global rules arrive under the `policy` payload key; per-interface rules under
  `interface_config`. The canonical zone tuple lives once on the domain as `OpPolicy.ZONES`.
- **Rule removal** is `no <zone> <network...>` (schema `type: "negate"`, handler `handle_remove` →
  `RemoveRuleUseCase`). It is **shell-only**: `build_parser` only attaches `type=="setting"` entries
  as POSIX flags, so a `negate` command never gets one.
- **Zone-name asymmetry:** the JSON/API/command zone is singular `target`, but the in-memory
  attribute is `raw_targets` and `OpPolicy.compile()` emits plural `targets`. Easy to mishandle.
- **Keep the domain pure:** `OpPolicy.compile()` receives the parser as an argument; don't import
  `IPParser` into `domain/models/`.
- **Validation lives in the domain.** `domain/services/validators.py` (hostname/MAC/IP/DNS/interface/
  port) is pure and reused by both the OS providers and playbook import. Playbook import runs
  `_validate_structure` (shapes) then `domain/services/playbook_validator.validate_playbook` (field
  values, collecting every error). Valid provider names come from `BackendConfig.VALID_PROVIDERS`
  (also the source of the `backend` command's choices). A playbook may carry an optional `meta` block
  → `OpProfile.meta` (`MissionMeta`); it's emitted to `session.json` only when present and shown in
  the `show` **Mission** section. See `PLAYBOOK.md`.
- **`session.json` is per-CWD** and gitignored (transient, per-machine staged state).

### Known rough edges (verified, as of v0.1.0)

These are real and worth knowing when working in the code — they are not yet fixed:

- `IptablesProvider.apply_ipv6_blocks/allows` are `pass` (no-ops) — IPv6 firewalling is silently not
  applied under iptables (would need `ip6tables`). Tracked in #20.
- **The `firewalld` provider may not filter at all**: `flush_managed_rules` creates an `opctl` zone
  but never binds an interface to it, `_add_rich_rule` ignores the `interface` arg and matches
  `source` (not `destination`/egress). So global/per-interface/`isolate` rules may be inert or
  mis-scoped under firewalld. `iptables`/`ufw` honor `-o interface` + egress correctly; `unmanaged
  isolate` therefore works on those two, not firewalld. Tracked in #33.
