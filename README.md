# opctl

**Tactical, cross-platform network configurator.** Stage hostname, MAC, IP, DNS, firewall, and NTP
changes to a JSON file, review them against the live system, then commit them to the OS on demand.

opctl runs on **Linux** and **Windows**, ships as **pure Python standard library** (zero third-party
dependencies), and exposes two front-ends over the same core: a one-shot POSIX CLI and an
interactive, Cisco-IOS-style shell.

> **Status:** early (v0.1.0). The staging engine, status diffing, and the Linux/Windows commit
> backends are functional. See [Project status](#project-status) for what is and isn't wired up yet.

---

## Why opctl?

Most network tooling applies changes the moment you type them. opctl follows a **stage-then-commit**
model instead:

1. **Stage** your intended configuration into `session.json` — nothing touches the hardware yet.
2. **Review** the difference between your staged intent and the real OS state (`[ SYNC ]` /
   `[ DIFF ]` per field).
3. **Commit** the whole profile to the operating system in one explicit step.

This makes changes reviewable and atomic-at-commit rather than applied piecemeal — useful when you
are reconfiguring a host's network posture and want to see the full delta before pulling the trigger.

## Features

- **Hostname** management.
- **Per-interface** configuration: MAC address (including `random`), static IPv4/IPv6 or DHCP, DNS,
  and administrative up/down.
- **Zone-based egress firewall** — `trusted` / `target` (allow) and `excluded` (deny, overrides),
  compiled with real subnet algebra (exclusion + CIDR collapsing) for IPv4 and IPv6, with optional
  `IP:PORT` overrides.
- **NTP** enable/disable.
- **Cross-platform** via auto-detected providers — it uses whatever network stack your host actually
  has (NetworkManager/iproute2/net-tools and firewalld/ufw/iptables on Linux; PowerShell/netsh/wmic
  on Windows).
- **Staged-vs-live diffing** before you commit.
- **Zero dependencies**, no build step, single `session.json` for all staged state.

## Installation

Requires **Python 3.8+**. Nothing else for the tool itself.

```bash
# From a clone of this repo:
pip install -e .          # installs the `opctl` console command

# …or run it in place without installing:
python opctl.py
```

## Quick start

### Interactive shell

Run `opctl` with no arguments to drop into the modal shell. The prompt shows your current mode.

```text
$ opctl
opctl# configure
opctl(config)# system
opctl(config-system)# hostname recon-01        # stage the hostname
opctl(config-system)# exit
opctl(config)# interface eth0                  # configure NIC eth0
opctl(config-if:eth0)# mode static
opctl(config-if:eth0)# ip 10.10.0.5/24
opctl(config-if:eth0)# mac random              # spoof a random MAC
opctl(config-if:eth0)# dns 1.1.1.1 9.9.9.9
opctl(config-if:eth0)# exit
opctl(config)# exit
opctl# show                                    # diff staged config against the live system
opctl# execute                                 # commit everything to the OS (needs root/admin)
```

Each setting prints a confirmation as it is staged (elided above). Navigation: `configure` enters
config mode; `system` / `ntp` / `policy` / `interface <name>` enter
sub-modes; `exit` (or `quit`) moves up one level, and at the root it exits the shell (so does
Ctrl+D). Commands accept unique prefixes (e.g. `conf`, `int eth0`). Type `help` in any mode for the
commands valid there.

### One-shot POSIX CLI

System settings and the stage/commit actions are available non-interactively:

```bash
opctl system --hostname recon-01    # stage the hostname
opctl system --dns 1.1.1.1 9.9.9.9  # stage global DNS
opctl show                          # show the staged-vs-live diff
opctl execute                       # commit staged config to the OS (run with sudo / as admin)
```

Per-interface configuration (MAC/IP/mode/DNS) and NTP are best done from the interactive shell — the
one-shot POSIX path for those is not reliable yet (see [Project status](#project-status)).

> Committing changes shells out to privileged OS tools (`ip`, `nmcli`, `iptables`, `hostnamectl`,
> PowerShell cmdlets, …), so `execute` must be run with root/administrator privileges.

## How it's organized

opctl uses a layered / hexagonal (ports-and-adapters) design; the domain has no outward
dependencies.

```
Front-ends   POSIX CLI  +  interactive shell      (both generated from one command schema)
     │
     ▼
Use cases    load staged state → mutate → save, or drive the OS backend
     ├─────────────► JSON repository  ↔  session.json   (staged state)
     └─────────────► OS backend → providers → OS CLI tools   (live system)
     ▲
Domain       models (profile + firewall policy), IP parser, ports, exceptions
```

Each OS **backend** is a thin facade that auto-resolves three **providers** — one each for the
system, network, and firewall concerns — picking the first tool available on the host (or one you
pin explicitly):

| Concern | Linux (auto-detect order) | Windows (auto-detect order) |
|---|---|---|
| hostname | `hostnamectl` → `hostname` | PowerShell → `wmic` |
| network  | `nmcli` → `iproute2` → `ifconfig` | PowerShell → `netsh` |
| firewall | `firewalld` → `ufw` → `iptables` | PowerShell → `netsh` |

Pin a provider by setting the `backend` block in `session.json` (e.g.
`"firewall_provider": "iptables"`); the default `"auto"` auto-detects.

## The `session.json` file

All staged state lives in a single JSON file, resolved relative to the directory you run opctl from
(and gitignored — it's per-machine, transient). Its shape:

```json
{
  "system":  { "hostname": "recon-01", "unmanaged_policy": "ignore" },
  "network": { "global_dns": [], "default_gateway": "", "ipv6_enabled": true, "ip_forwarding": false },
  "ntp":     { "enabled": false, "servers": [] },
  "interfaces": {
    "eth0": {
      "name": "eth0", "enabled": true, "mac_address": "", "randomize_mac": true,
      "mode": "static", "ip_addresses": ["10.10.0.5/24"], "gateway": "", "dns_servers": ["1.1.1.1"],
      "dhcp_ignore_dns": false, "dhcp_ignore_gw": false,
      "policy": { "trusted": [], "target": [], "excluded": [] }
    }
  },
  "global_policy": { "trusted": [], "target": [], "excluded": [] },
  "backend": { "firewall_provider": "auto", "network_provider": "auto", "system_provider": "auto" }
}
```

The firewall **zones** live in `global_policy` (host-wide) and in each interface's `policy`
(bound to that NIC). Each accepts CIDRs, splat (`192.168.*.10`) and dash-range (`192.168.0-5.10`)
notation for IPv4, strict CIDR for IPv6, and `IP:PORT` for port-scoped rules. At commit time,
`excluded` is subtracted from `trusted`/`target` and the result is collapsed into minimal CIDR sets.

## Development

```bash
pip install -e .          # editable install
pip install pytest        # the test suite's only extra dependency

python -m pytest tests/                                    # run everything
python -m pytest tests/test_policy.py                      # one file
python -m pytest tests/test_policy.py::TestOpPolicy::test_compile_with_exclusions   # one test
```

There is no build/compile step. Adding a command or flag is a single edit to
`opctl/command_schema.py` — both front-ends are generated from that schema.

## Project status

opctl is at **v0.1.0** and under active development. Working today: staging via the **interactive
shell** (hostname, per-interface MAC/IP/mode/DNS/up-down, NTP enable/disable); the **one-shot POSIX
CLI** for system settings (`--hostname`, `--dns`, `--unmanaged`) plus the `show` and `execute`
actions; staged-vs-live diffing (`show`); and committing to Linux and Windows hosts (`execute`).
Still being wired up:

- **Firewall zone rules currently have no dedicated CLI/shell command** — the policy engine and
  commit path are complete, but zones are populated by editing the `global_policy` / interface
  `policy` blocks in `session.json` directly.
- **Per-interface and NTP configuration via the one-shot POSIX CLI is not reliable yet** — the
  `enable`/`disable` flag defaults leak through and stage the interface (or NTP) as disabled. Use the
  interactive shell for these.
- IPv6 firewalling is a no-op under the `iptables` provider specifically (use `firewalld`/`ufw` for
  IPv6 blocking).

## License

Distributed under the **GNU GPLv3**. See [`LICENSE`](LICENSE).

## Author

Stephen Trotter — <stephen.j.trotter@gmail.com>
<https://github.com/sjtrotter/opctl>
