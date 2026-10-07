# Ansible Role: networking

Foundational workstation network interface, DNS, and connection profile orchestration across Fedora, AlmaLinux, and Rocky Linux.

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `networking` role operates at **Layer 1 (Ansible Machine Orchestration)** within `playbooks/workstation.yml` and `local.yml`. It provides the foundational host network orchestration layer beneath higher-level virtualization and network service roles (`libvirt`, `containerd`, `nas`).

```
+--------------------------------------------------------------------------+
|                  Higher-Layer Network Services (Layer 1)                 |
|     roles/nas (NFS/Samba/Rsync), roles/libvirt (virbr0), containerd      |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Layer 1: roles/networking (Ansible)                  |
|   - Workstation Host Networking Baseline & Connection Orchestration      |
|   - NetworkManager & systemd-resolved Profile Foundations                |
|   - Formal Argument Specification & Schema Validation                    |
|   - Tag-as-Select Orchestration Entry Point                              |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|            Physical NICs, Linux Kernel Routing, NetworkManager           |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary task coordinator.
2. **Tag-as-Select Pattern**: Tasks are tagged with domain tags (`networking`, `system`, `always`) allowing targeted partial runs or execution as part of the broader system play.
3. **Formal Argument Specification Pattern**: Uses `meta/argument_specs.yml` for compile-time parameter validation and type enforcement.
4. **Debug-as-Progress-Indicator Pattern**: Role entry announces execution start via `ansible.builtin.debug` tagged `["always"]`.
5. **Two-Tier Variable Scoping**: Variables strictly adhere to the `networking_*` namespace (Tier 2 scope).

---

## Role Status & Capabilities

The role currently serves as the verified baseline networking hook in the workstation orchestration pipeline:

- **Active Pipeline Integration**: Executed on every `workstation.yml` and `local.yml` run prior to container and virtualization roles.
- **Validation**: Enforces argument specifications via `meta/argument_specs.yml`.
- **Target Subsystems** (for site-specific extension): NetworkManager keyfile management, static DNS configuration via `systemd-resolved`, interface MTU tuning, and custom routing policies.

---

## Role Variables

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `networking_*` and control role-specific behavior:

| Variable | Default | Type | Description |
|---|---|---|---|
| `networking_my_variable` | `"default_value"` | `string` | Baseline role configuration parameter validated against `meta/argument_specs.yml`. |

---

## Argument Specifications (`meta/argument_specs.yml`)

The role declares formal argument specifications validated by Ansible Core:

```yaml
argument_specs:
  main:
    short_description: Workstation network configuration role.
    options:
      networking_my_variable:
        type: str
        description: A simple string argument for demonstration and role validation.
        default: "default_value"
```

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `networking` | Role | Applies to all tasks within the `networking` role. |
| `system` | Playbook | System configuration group tag shared across `tuning`, `networking`, `desktop`. |
| `always` | System | Preamble debug logging. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included in `playbooks/workstation.yml` as part of the base system configuration stage:

```yaml
- name: System Configuration
  hosts: workstations
  become: true
  roles:
    - role: tuning
      tags: ["tuning", "system"]
    - role: networking
      tags: ["networking", "system"]
    - role: containerd
      tags: ["containerd", "virt"]
    - role: desktop
      tags: ["desktop", "system"]
    - role: libvirt
      tags: ["libvirt", "virt"]
```

### 2. Autonomous Local Provisioning (`local.yml`)

In `local.yml`, executed during local workstation bootstrap:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: networking
      tags: ["networking", "system"]
```

### 3. Execution Commands

Run only the networking role:

```bash
ansible-playbook playbooks/workstation.yml --tags "networking"
```

---

## Verification & Health Checks

Verify host networking and interface state:

```bash
# Check NetworkManager service state
systemctl status NetworkManager.service

# List active network connections
nmcli connection show

# Inspect DNS resolution status
resolvectl status
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/networking
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
