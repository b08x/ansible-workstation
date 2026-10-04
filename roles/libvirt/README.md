# Ansible Role: libvirt

Hardware-accelerated KVM / QEMU virtualization engine orchestration, daemon security configuration, QEMU bridge networking, storage pool tuning, user permissions, and Docker network conflict resolution across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `libvirt` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy and configure hardware-accelerated hypervisor services (`libvirtd`), allowing developers to run ephemeral virtual machines, test clusters, and guest appliances completely isolated from the workstation host operating system.

```
+--------------------------------------------------------------------------+
|                     Layer 2: Guest Virtual Machines                      |
|          Vagrant Boxes, Test Appliances, Kernel Build Sandboxes          |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/libvirt (Ansible)                    |
|   - Virtualization Package Group (@virtualization)                       |
|   - Libvirt Daemon Configuration (/etc/libvirt/libvirtd.conf)            |
|   - Passwordless Socket Access (UNIX Domain Socket + libvirt group)      |
|   - QEMU Bridge Helper ACLs (/etc/qemu/bridge.conf)                      |
|   - LVM Storage Pool Integration (use_lvmetad = 0 in /etc/lvm/lvm.conf)  |
|   - Docker & Libvirt Network Conflict Resolution (DOCKER-USER iptables)  |
|   - User Group Management (libvirt, qemu groups)                         |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|            Hardware Virtualization (Intel VT-x / AMD-V, /dev/kvm)        |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the dispatcher coordinating core provisioning with dedicated subtasks (`network_conflicts.yml`).
2. **Distro-Switching Pattern (Dialect A)**: Dynamic OS-specific variable inclusion via `vars/{{ ansible_distribution }}.yml`, defining `libvirt_packages` (`@virtualization`) and `libvirt_bridge_conf_path` across Fedora, AlmaLinux, and Rocky Linux.
3. **Pre-flight Capability Checks**: `tasks/network_conflicts.yml` probes for `iptables` and checks the existence of the `DOCKER-USER` chain before attempting rule manipulation, ensuring non-fatal, safe convergence on systems running nftables-only or without Docker.
4. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`libvirt`, `virt`) and granular feature tags (`install`, `config`, `qemu`, `lvm`, `users`, `service`, `kvm`, `docker`, `network`).
5. **Backup-on-Write Pattern**: All templated or modified configuration files (`/etc/libvirt/libvirtd.conf`, `/etc/qemu/bridge.conf`, `/etc/lvm/lvm.conf`) specify `backup: true` to prevent data loss.
6. **Handler Notification Pattern**: Changes to `/etc/libvirt/libvirtd.conf` notify `Restart libvirtd`.
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `use_kvm`) and Tier 2 role-namespaced variables (`libvirt_*`).

---

## Core Components & Subsystems

### 1. Virtualization Engine & Package Installation (`tasks/main.yml`)
- Deploys the system `@virtualization` package group containing QEMU, KVM kernel module utilities, Libvirt daemons, client tools (`virsh`, `virt-install`), and virt-manager.
- Validates OS-specific paths via `vars/{{ ansible_distribution }}.yml`.

### 2. Libvirt Daemon & Socket Permissions (`templates/etc/libvirt/libvirtd.conf.j2`)
- Configures `/etc/libvirt/libvirtd.conf` to enable passwordless management for non-root users in the `libvirt` group:
  - `unix_sock_group = "{{ libvirt_unix_sock_group }}"` (defaults to `libvirt`)
  - `unix_sock_rw_perms = "{{ libvirt_unix_sock_rw_perms }}"` (defaults to `"0770"`)
  - `auth_unix_rw = "{{ libvirt_auth_unix_rw }}"` (defaults to `"none"`)
- Establishes keepalive intervals (`keepalive_interval = 5`, `keepalive_count = 5`) to detect dead clients and maintain stable connection states.

### 3. QEMU Bridge Helper Configuration (`files/etc/qemu/bridge.conf`)
- Deploys `/etc/qemu/bridge.conf` with `allow virbr0` permissions.
- Enables unprivileged guest virtual machines to attach to the default NAT bridge (`virbr0`) without requiring full root elevation for network interfaces.

### 4. LVM Storage Pool Tuning (`tasks/main.yml`)
- Libvirt storage pools managing logical volumes can fail or conflict with host metadata caching daemons.
- When `libvirt_configure_lvm: true`, configures `use_lvmetad = 0` in `/etc/lvm/lvm.conf` to avoid metadata locking conflicts during VM volume creation and snapshots.

### 5. User Group Management (`tasks/main.yml`)
- Appends target workstation users (`libvirt_users`, defaulting to `{{ user.name }}`) to the `libvirt` group.
- Additionally adds the workstation user to both `libvirt` and `qemu` groups to ensure complete access to `/dev/kvm`, disk images, and serial sockets.

### 6. Docker & Libvirt Network Conflict Resolution (`tasks/network_conflicts.yml`)
- Docker alters the host's `iptables` FORWARD chain policy to `DROP`, which by default breaks bridge packet routing for Libvirt guest virtual machines on `virbr0`.
- Probes for `iptables` and the `DOCKER-USER` chain.
- Injects `ACCEPT` rules into the `DOCKER-USER` chain for both inbound (`in_interface: virbr+`) and outbound (`out_interface: virbr+`) virtualization traffic.
- Ensures seamless coexistence where both Docker containers and Libvirt virtual machines communicate across host bridges simultaneously.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Distro Variable File** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky.yml` |
| **Package Group** | `@virtualization` | `@virtualization` | `@virtualization` |
| **Service Name** | `libvirtd.service` | `libvirtd.service` | `libvirtd.service` |
| **Bridge Config Path** | `/etc/qemu/bridge.conf` | `/etc/qemu/bridge.conf` | `/etc/qemu/bridge.conf` |
| **LVM Tuning** | Supported (`use_lvmetad = 0`) | Supported (`use_lvmetad = 0`) | Supported (`use_lvmetad = 0`) |
| **Docker Interop Fix** | `DOCKER-USER` iptables | `DOCKER-USER` iptables | `DOCKER-USER` iptables |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT). |
| `use_kvm` | `true` | Hardware capability flag indicating KVM virtualization support. |
| `auto_enable_libvirt` | `true` | Capability flag evaluated during `local.yml` preflight checks to gate role execution. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `libvirt_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `libvirt_service` | `"libvirtd.service"` | Name of the primary Libvirt systemd service unit. |
| `libvirt_service_enabled` | `true` | Whether to enable and start the Libvirt service. |
| `libvirt_users` | `["{{ user.name }}"]` | User accounts added to the `libvirt` group. |
| `libvirt_unix_sock_group` | `"libvirt"` | UNIX domain socket group ownership in `libvirtd.conf`. |
| `libvirt_unix_sock_rw_perms` | `"0770"` | UNIX domain socket read-write permissions. |
| `libvirt_auth_unix_rw` | `"none"` | Authentication scheme for UNIX read-write sockets (`"none"` permits group members). |
| `libvirt_configure_lvm` | `true` | Whether to set `use_lvmetad = 0` in `/etc/lvm/lvm.conf`. |

### Tier 2: Distribution Variables (`vars/*.yml`)

Loaded dynamically from `vars/{{ ansible_distribution }}.yml`:

| Variable | Type | Description |
|---|---|---|
| `libvirt_packages` | `list` | Distribution-specific virtualization package list or package group. |
| `libvirt_bridge_conf_path` | `string` | Filesystem location for the QEMU bridge ACL configuration. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `libvirt` | Role | Applies to all tasks within the `libvirt` role. |
| `virt` | Playbook | Tag grouping container and virtualization roles (`containerd`, `libvirt`). |
| `install` | Feature | Executes `@virtualization` package installation. |
| `config` | Feature | Deploys `/etc/libvirt/libvirtd.conf` and QEMU bridge settings. |
| `qemu` | Feature | Configures QEMU bridge access. |
| `lvm` | Feature | Applies LVM storage pool configuration to `/etc/lvm/lvm.conf`. |
| `users` | Feature | Manages user group assignments (`libvirt`, `qemu`). |
| `service` | Feature | Enables and starts the `libvirtd.service` systemd unit. |
| `network` | Feature | Resolves Docker/Libvirt iptables forwarding conflicts. |
| `docker` | Feature | Targets Docker interoperability tasks in `network_conflicts.yml`. |
| `kvm` | Feature | Aliases virtualization and bridge tasks. |
| `always` | System | Preamble debug statements and OS variable inclusion. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included within `playbooks/system.yml` as part of the virtualization stack:

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

In `local.yml`, hardware preflight checks detect CPU virtualization extensions (`/dev/kvm`) and gate execution:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: libvirt
      when: auto_enable_libvirt | default(true) | bool
      tags: ["libvirt", "virt"]
```

### 3. Execution Commands

Run only the libvirt role during a workstation convergence:

```bash
ansible-playbook playbooks/site.yml --tags "libvirt"
```

Reconfigure only user permissions and bridge access:

```bash
ansible-playbook local.yml --tags "users,qemu"
```

Apply Docker/Libvirt network conflict rules:

```bash
ansible-playbook local.yml --tags "network,docker"
```

---

## Verification & Health Checks

After role convergence, verify hypervisor health using standard Libvirt CLI commands:

### 1. Daemon & Hypervisor Connectivity

```bash
# Verify connection to local QEMU/KVM hypervisor as non-root user
virsh uri
# Output should be: qemu:///system

# Verify libvirtd daemon status
systemctl status libvirtd.service

# List active and inactive virtual machines
virsh list --all
```

### 2. Network & Bridge Verification

```bash
# Verify default virtual network status
virsh net-list --all

# Inspect default network details
virsh net-info default

# Check QEMU bridge permissions
cat /etc/qemu/bridge.conf
```

### 3. Docker Interoperability Check

```bash
# Check DOCKER-USER chain rules for virbr bridge acceptance
iptables -L DOCKER-USER -n -v
```

### 4. Group Membership Verification

```bash
# Verify workstation user is in the libvirt and qemu groups
groups $USER
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/libvirt
```

Execute role unit testing via the provided test play:

```bash
ansible-playbook roles/libvirt/tests/test.yml -i roles/libvirt/tests/inventory --check
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
