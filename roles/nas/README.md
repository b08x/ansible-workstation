# Ansible Role: nas (Network Attached Storage)

Enterprise network storage orchestration provisioning NFSv4 server, Samba/SMB file sharing, and Rsync daemon services with co-located firewalld rules and multi-tenant access controls across Fedora, AlmaLinux, and Rocky Linux.

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `nas` role operates at **Layer 1 (Ansible Machine Orchestration)** to provision persistent network file systems and synchronization endpoints. It enables workstations and local compute clusters to access shared assets, datasets, media libraries, and backup repositories with predictable permissions and locked-down network access.

```
+--------------------------------------------------------------------------+
|                     Layer 2: Network Storage Consumers                   |
|       Workstation Fleets, Container Storage Mounts, Backup Pipelines     |
+--------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            | (NFSv4 Protocol)      | (SMB/CIFS Protocol)   | (rsync Protocol)
            v                       v                       v
+--------------------------------------------------------------------------+
|                        Layer 1: roles/nas (Ansible)                      |
|   - NFSv4 Daemon Stack (nfs-utils, rpcbind, idmapd, /etc/exports)        |
|   - Samba File Sharing (smbd, nmbd, /etc/samba/smb.conf)                 |
|   - Rsync Daemon (rsync-daemon, /etc/rsyncd.conf)                        |
|   - Dedicated System Users & Service Accounts (nobody, smbuser)          |
|   - Co-located Hybrid Firewall Rules (Services + Fixed Daemon Ports)     |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Storage                |
|             ZFS, XFS, Btrfs Local Disks & Filesystem Mounts              |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to isolated subsystem coordinators (`packages.yml`, `users.yml`, `nfs/main.yml`, `samba/main.yml`, `rsync/main.yml`) gated by explicit boolean flags (`nas_enable_nfs`, `nas_enable_samba`, `nas_enable_rsync`).
2. **Distro-Switching Pattern (Dialect A)**: Dynamic OS-specific package and service variable inclusion via `vars/{{ ansible_distribution }}.yml` with fallback to `vars/RedHat.yml`.
3. **Data-Driven Directory Creation**: Storage export and share definitions dynamically create parent directories, ownership, and permissions when `create_dir: true`.
4. **Data-Driven Firewall Pattern**: Implements co-located firewall rules directly within `nfs/firewall.yml` and `samba/firewall.yml` using `ansible.posix.firewalld`, managing both standard services and fixed static ports to eliminate ephemeral port collisions.
5. **Backup-on-Write Pattern**: All templated configuration files (`/etc/exports`, `/etc/nfs.conf`, `/etc/idmapd.conf`, `/etc/samba/smb.conf`, `/etc/rsyncd.conf`) set `backup: true` to protect administrative modifications.
6. **Handler Notification Pattern**: Configuration changes notify granular reload and restart handlers (`Reload NFS exports` via `exportfs -arv`, `Restart NFS server`, `Restart Samba`, `Restart rsync daemon`, `Reload firewalld`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 domain-level network settings (`ansible_domain`, `firewall.nfs.ports`) and Tier 2 namespaced role variables (`nas_*`).

---

## Core Components & Subsystems

### 1. NFS Server (`tasks/nfs/`)
**Enabled by default** (`nas_enable_nfs: true`).
- **NFSv4 Pseudo-Root**: Configures NFSv4 pseudo-root export (`fsid=0`) in `/srv/nfs` and nested exported paths.
- **ID Mapping**: Templates `/etc/idmapd.conf` with dynamic domain binding (`nas_nfs_domain`).
- **Fixed Daemon Ports**: Enforces deterministic daemon ports in `/etc/nfs.conf` (lockd: `32803/tcp`, `32769/udp`; mountd: `892`; statd: `662`) to prevent firewall breakage caused by random RPC port allocations.
- **Export Management**: Deploys `/etc/exports` with network CIDR restrictions (`nas_nfs_allowed_networks`) and notifies `exportfs -arv` for zero-downtime export table reloads.
- **Co-located Firewall**: Activates firewalld services (`nfs`, `rpc-bind`, `mountd`) and opens explicit auxiliary daemon ports.

### 2. Samba / SMB Server (`tasks/samba/`)
**Disabled by default** (`nas_enable_samba: false`).
- **Service Stack**: Deploys `samba`, `samba-common`, and `samba-client`.
- **Global Settings**: Configures `/etc/samba/smb.conf` with workgroup, NetBIOS name, protocol minimums (`nas_samba_server_min_protocol: NT1` to `SMB3`), and NTLM authentication settings.
- **Multi-Share Configuration**: Dynamically defines shares from the `nas_samba_shares` dictionary with valid user restrictions, write lists, guest access flags, and inheritance masks.
- **System Accounts**: Configures dedicated Samba user accounts (`nas_samba_user`, default: `smbuser`) and system groups.
- **Co-located Firewall**: Opens `samba` firewalld service (TCP 139, 445; UDP 137, 138) and optional `samba-client`.

### 3. Rsync Daemon (`tasks/rsync/`)
**Disabled by default** (`nas_enable_rsync: false`).
- **Service Configuration**: Deploys `rsync-daemon` packages and templates `/etc/rsyncd.conf`.
- **Modular Shares**: Dynamically generates rsync module definitions with `hosts allow`, `hosts deny`, read-only flags, and max connection throttles.
- **Unprivileged Execution**: Configures the daemon to execute under `nobody:nobody` with chroot isolation options.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Distro Variable File** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky.yml` |
| **NFS Packages** | `nfs-utils` | `nfs-utils` | `nfs-utils` |
| **Samba Packages** | `samba`, `samba-common-tools` | `samba`, `samba-common-tools` | `samba`, `samba-common-tools` |
| **Rsync Packages** | `rsync-daemon` | `rsync-daemon` | `rsync-daemon` |
| **NFS Service Name** | `nfs-server.service` | `nfs-server.service` | `nfs-server.service` |
| **Samba Service Name** | `smb.service`, `nmb.service` | `smb.service`, `nmb.service` | `smb.service`, `nmb.service` |
| **Firewall Management** | `ansible.posix.firewalld` | `ansible.posix.firewalld` | `ansible.posix.firewalld` |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, network domain context, or centralized port mappings in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `ansible_domain` | `localdomain` | Workstation DNS domain used for NFSv4 ID mapping in `/etc/idmapd.conf`. |
| `firewall.nfs.ports` | *(dictionary)* | Global definition of fixed daemon ports for RPC, lockd, mountd, and statd. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `nas_*` and control role-specific behavior:

#### Subsystem Activation Flags
| Variable | Default | Description |
|---|---|---|
| `nas_enable_nfs` | `true` | Enable and configure the NFSv4 server stack. |
| `nas_enable_samba` | `false` | Enable and configure Samba/SMB file sharing. |
| `nas_enable_rsync` | `false` | Enable and configure the Rsync daemon. |

#### NFS Configuration Variables
| Variable | Default | Description |
|---|---|---|
| `nas_nfs_user_name` | `"nobody"` | System user for unprivileged NFS operations. |
| `nas_nfs_user_group` | `"nobody"` | System group for unprivileged NFS operations. |
| `nas_nfs_user_uid` | `65534` | UID for the NFS user. |
| `nas_nfs_user_gid` | `65534` | GID for the NFS group. |
| `nas_nfs_domain` | `{{ ansible_domain \| default('localdomain') }}` | Domain for NFSv4 ID mapping. |
| `nas_nfs_allowed_networks` | `["192.168.41.0/24"]` | List of network CIDRs permitted to mount NFS exports. |
| `nas_nfs_export_options` | `["rw", "sync", "no_subtree_check"]` | Default options applied to exports. |
| `nas_nfs_root_export_options`| `["rw", "fsid=0", "no_subtree_check", "sync"]` | Options for the pseudo-root export. |
| `nas_nfs_exports` | `[{path: /srv/nfs, create_dir: true, is_root: true}]` | List of export dictionaries. |

#### Samba Configuration Variables
| Variable | Default | Description |
|---|---|---|
| `nas_samba_user` | `"smbuser"` | Primary Samba username. |
| `nas_samba_group` | `"smbgroup"` | Primary Samba group name. |
| `nas_samba_uid` | `1036` | UID for the Samba user. |
| `nas_samba_gid` | `1036` | GID for the Samba group. |
| `nas_samba_workgroup` | `"WORKGROUP"` | SMB workgroup name. |
| `nas_samba_server_string` | `"Samba Server %v"` | Server description string. |
| `nas_samba_hosts_allow` | `["127.0.0.1", "192.168.41.0/24"]` | Allowed clients for SMB shares. |
| `nas_samba_shares` | *(see defaults/main.yml)* | List of defined SMB share dictionaries. |
| `nas_samba_enable_nmb` | `true` | Enable NetBIOS name service daemon (`nmb`). |

#### Rsync Configuration Variables
| Variable | Default | Description |
|---|---|---|
| `nas_rsync_user` | `"nobody"` | User for rsync file operations. |
| `nas_rsync_group` | `"nobody"` | Group for rsync file operations. |
| `nas_rsync_max_connections` | `4` | Maximum concurrent connections. |
| `nas_rsync_use_chroot` | `false` | Whether to enable chroot in rsyncd. |
| `nas_rsync_modules` | *(see defaults/main.yml)* | List of rsync module dictionaries. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `nas` | Role | Applies to all tasks within the `nas` role. |
| `nas_packages` | Feature | Executes package installation for enabled storage services. |
| `nas_users` | Feature | Provisions storage system users and groups. |
| `nas_nfs` | Subsystem | Orchestrates all NFS configuration, exports, services, and firewall rules. |
| `nas_samba` | Subsystem | Orchestrates all Samba configuration, shares, services, and firewall rules. |
| `nas_rsync` | Subsystem | Orchestrates all Rsync daemon configuration and service management. |
| `nfs_config` | Component | Updates `/etc/exports` and NFS configuration files. |
| `samba_config` | Component | Updates `/etc/samba/smb.conf`. |
| `rsync_config` | Component | Updates `/etc/rsyncd.conf`. |
| `firewall` | Component | Applies co-located firewalld service and port rules. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

```yaml
- name: Configure Network Storage Services
  hosts: storage_servers
  become: true
  roles:
    - role: nas
      vars:
        nas_enable_nfs: true
        nas_enable_samba: true
        nas_nfs_allowed_networks:
          - "192.168.1.0/24"
        nas_nfs_exports:
          - path: /srv/nfs
            create_dir: true
            is_root: true
          - path: /srv/nfs/datasets
            create_dir: true
            options: ["rw", "sync", "no_subtree_check"]
        nas_samba_shares:
          - name: datasets
            path: /srv/nfs/datasets
            comment: Shared Machine Learning Datasets
            browseable: true
            public: false
```

### 2. Execution Commands

Converge only NAS role tasks:

```bash
ansible-playbook playbooks/site.yml --tags "nas"
```

Reconfigure only NFS exports without touching services:

```bash
ansible-playbook playbooks/site.yml --tags "nfs_config"
```

Update Samba configuration and restart daemon:

```bash
ansible-playbook playbooks/site.yml --tags "nas_samba"
```

---

## Verification & Health Checks

After role convergence, verify storage services and exports:

### 1. NFS Verification

```bash
# Verify NFS service status
systemctl status nfs-server.service

# Inspect exported filesystems
exportfs -v

# Probe RPC service registrations
rpcinfo -p localhost

# Test local mount of NFSv4 export
mkdir -p /mnt/test-nfs
mount -t nfs4 localhost:/ /mnt/test-nfs
ls -la /mnt/test-nfs
umount /mnt/test-nfs
```

### 2. Samba Verification

```bash
# Verify Samba services
systemctl status smb.service nmb.service

# Test smb.conf syntax
testparm -s

# List local shares via smbclient
smbclient -L localhost -N
```

### 3. Rsync Daemon Verification

```bash
# Verify rsync daemon status
systemctl status rsyncd.service

# Query advertised modules
rsync localhost::
```

### 4. Firewall Verification

```bash
# Verify firewalld active rules for NFS and Samba
firewall-cmd --list-services
firewall-cmd --list-ports
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/nas
```

Execute role unit testing via the provided test play:

```bash
ansible-playbook roles/nas/tests/test.yml -i roles/nas/tests/inventory --check
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
