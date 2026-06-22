# opctl Playbook Format

A **playbook** is a JSON file describing a staged opctl session. It is the same shape opctl
serializes to `session.json`, so any exported session is a valid playbook:

```bash
opctl write mission.json     # export the current staged session as a playbook
opctl import mission.json     # load a playbook (replaces the staged session)
```

`import` **replaces** the staged session (it does not merge), validates the playbook, and — only if
it is valid — writes it to `session.json`. Nothing is applied to the OS until you run `execute`.

## Top-level structure

```jsonc
{
  "meta":          { ... },   // optional — playbook identity / provenance
  "system":        { ... },   // hostname, unmanaged-interface policy
  "network":       { ... },   // global DNS, default gateway, toggles
  "ntp":           { ... },   // NTP enable + servers
  "interfaces":    { ... },   // per-NIC configuration, keyed by interface name
  "global_policy": { ... },   // host-wide firewall zones
  "backend":       { ... }    // OS provider selection (per-machine capability)
}
```

Every block is optional; missing blocks take their defaults. **Unknown keys are dropped** on import
(normalized away by the domain model). All blocks must be JSON **objects**, and every firewall zone
must be a JSON **list** — otherwise import fails with a structural error.

## `meta` — playbook identity (optional)

Metadata only; never applied to the OS. Present in `session.json` only when imported from a playbook
that carried it, and shown under the **Mission** section of `show`.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Playbook / mission name |
| `version` | integer | Playbook version (default `1`) |
| `description` | string | Free-text description |

## `system`

| Field | Type | Validation |
|---|---|---|
| `hostname` | string | RFC-1123 hostname (labels `[a-zA-Z0-9-]`, ≤253 chars) |
| `unmanaged_policy` | string | one of `ignore` (default), `isolate`, `disable` |

## `network`

| Field | Type | Validation |
|---|---|---|
| `global_dns` | list of strings | each a bare IP address |
| `default_gateway` | string | a bare IP / CIDR |
| `ipv6_enabled` | bool | default `true` |
| `ip_forwarding` | bool | default `false` |

## `ntp`

| Field | Type | Validation |
|---|---|---|
| `enabled` | bool | default `false` |
| `servers` | list of strings | each a hostname **or** IP address |

## `interfaces`

An object keyed by interface name (e.g. `"eth0"`). Each value:

| Field | Type | Validation |
|---|---|---|
| `enabled` | bool | default `true`; `false` brings the NIC down |
| `mode` | string | one of `dhcp` (default), `static` |
| `mac_address` | string | `AA:BB:CC:DD:EE:FF` (`:` or `-` separators) |
| `randomize_mac` | bool | spoof a random MAC instead of a fixed one |
| `ip_addresses` | list of strings | each a bare IP / CIDR |
| `gateway` | string | a bare IP / CIDR |
| `dns_servers` | list of strings | each a bare IP |
| `policy` | object | per-interface firewall zones (see below) |

The interface **key** is authoritative — it must be a valid interface name (`[a-zA-Z0-9_.\- ]`,
1–64 chars) and overrides any inner `name`.

## Firewall policy (`global_policy` and interface `policy`)

Three zones, each a list of rules:

| Zone | Effect |
|---|---|
| `trusted` | allow |
| `target` | allow |
| `excluded` | deny — **overrides** `trusted`/`target` |

A **rule** is one of:

- a CIDR — `10.0.0.0/24`, `2001:db8::/32`
- a bare IP — `10.0.0.5` (treated as `/32`)
- IPv4 **splat** — `192.168.*.10` (per-octet wildcard)
- IPv4 **dash-range** — `192.168.0-5.10`
- any of the above with a **port** — `10.0.0.5:443`, `[2001:db8::1]:443`

> IPv6 supports strict CIDR only (no splat/dash). At commit time, `excluded` is subtracted from
> `trusted`/`target` and the result is collapsed into minimal CIDR sets.

## `backend` — provider selection

Per-machine capability (which OS tool drives each concern); `auto` auto-detects.

| Field | Valid values |
|---|---|
| `firewall_provider` | `auto`, `iptables`, `firewalld`, `ufw`, `powershell`, `netsh` |
| `network_provider` | `auto`, `iproute2`, `nmcli`, `ifconfig`, `powershell`, `netsh` |
| `system_provider` | `auto`, `hostnamectl`, `hostname`, `powershell`, `wmic` |
| `ntp_provider` | `auto`, `timesyncd`, `chrony`, `w32tm` |

## Validation

Import validates in two passes and **fails loudly** with a complete error list:

1. **Structural** — top-level is an object; each block is an object; every firewall zone is a list.
2. **Field-level** — hostnames, MACs, IPs/CIDRs, DNS servers, NTP servers, enums (`mode`,
   `unmanaged_policy`), provider names, and firewall rules (incl. `:PORT`) are all checked. Every
   problem found is reported at once.

A playbook that fails either pass is rejected and the staged session is left unchanged.

## Example

```json
{
  "meta": { "name": "recon-alpha", "version": 1, "description": "objective network sweep" },
  "system": { "hostname": "recon-01", "unmanaged_policy": "isolate" },
  "network": { "global_dns": ["1.1.1.1", "9.9.9.9"] },
  "ntp": { "enabled": true, "servers": ["0.pool.ntp.org"] },
  "interfaces": {
    "eth0": {
      "mode": "static",
      "randomize_mac": true,
      "ip_addresses": ["10.10.0.5/24"],
      "gateway": "10.10.0.1",
      "dns_servers": ["1.1.1.1"],
      "policy": { "trusted": [], "target": ["10.10.0.0/24"], "excluded": ["10.10.0.13"] }
    }
  },
  "global_policy": { "trusted": ["192.168.1.0/24"], "target": ["10.0.0.0/24:443"], "excluded": [] },
  "backend": { "firewall_provider": "iptables", "network_provider": "iproute2", "system_provider": "auto" }
}
```

## Versioning

`meta.version` is an integer that lets playbooks be tracked and, in future, migrated. The current
config schema is unversioned (it is the live `OpProfile` shape); a formal schema version may be added
alongside a mission-frontmatter format in a later release.
