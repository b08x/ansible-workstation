# Ansible Role: NAS (Network Attached Storage)

A comprehensive Ansible role for configuring network-attached storage services on **RedHat family** systems (Fedora, Rocky Linux 9, RHEL). This role supports NFS, Samba/SMB, and Rsync daemon services with fully variable-driven configuration.

## Table of Contents

- [Requirements](#requirements)
- [Supported Platforms](#supported-platforms)
- [Role Variables](#role-variables)
  - [Service Activation](#service-activation)
  - [NFS Configuration](#nfs-configuration)
  - [Samba Configuration](#samba-configuration)
  - [Rsync Configuration](#rsync-configuration)
- [Dependencies](#dependencies)
- [Example Playbook](#example-playbook)
- [Directory Structure](#directory-structure)
- [Usage Examples](#usage-examples)
- [Testing](#testing)
- [License](#license)

## Requirements

- **Ansible**: Version 2.12 or higher
- **Collections**:
  - `ansible.posix` (for firewalld module)
- **Operating System**: RedHat family only (Fedora, Rocky Linux 9, RHEL)

## Supported Platforms

| Platform | Versions |
|----------|----------|
| Fedora | All current versions |
| Rocky Linux | 9.x |
| RHEL | 9.x |

**Note**: This role is specifically designed for RedHat family distributions and will fail with an assertion error on other OS families.

## Role Variables

All variables are defined in `defaults/main.yml` with sensible defaults. See below for comprehensive documentation.

### Service Activation

Control which NAS services are enabled:

```yaml
# Enable/disable individual NAS services
nas_enable_nfs: true      # NFS server
nas_enable_samba: true    # Samba/SMB server
nas_enable_rsync: false   # Rsync daemon (disabled by default)
```

### NFS Configuration

#### NFS User/Group

```yaml
nas_nfs_user_name: nobody
nas_nfs_user_group: nobody
nas_nfs_user_uid: 65534
nas_nfs_user_gid: 65534
```

#### NFS Domain & Network Access

```yaml
# NFSv4 domain (defaults to system's DNS domain)
nas_nfs_domain: "{{ ansible_domain | default('localdomain') }}"

# Allowed networks (CIDR notation)
nas_nfs_allowed_networks:
  - "192.168.41.0/24"
  - "10.0.0.0/8"        # Add additional networks as needed
```

#### NFS Exports

Define NFS exports as a list of dictionaries:

```yaml
nas_nfs_exports:
  - path: /srv/nfs
    create_dir: true
    is_root: true  # NFSv4 pseudo-root (fsid=0)

  - path: /srv/nfs/shared
    create_dir: true
    owner: nobody
    group: nobody
    mode: '0755'
    options:  # Optional: override default export options
      - rw
      - nohide
      - insecure
      - no_subtree_check
      - sync
    clients:  # Optional: override default allowed networks
      - "192.168.1.0/24"
```

**Export Parameters**:
- `path` (required): Directory path to export
- `is_root` (optional): Mark as NFSv4 pseudo-root (fsid=0)
- `create_dir` (optional, default: false): Create directory if missing
- `owner` (optional, default: nas_nfs_user_name): Directory owner
- `group` (optional, default: nas_nfs_user_group): Directory group
- `mode` (optional, default: '0755'): Directory permissions
- `options` (optional): List of NFS export options (defaults to nas_nfs_export_options)
- `clients` (optional): List of allowed networks (defaults to nas_nfs_allowed_networks)

#### Default NFS Export Options

```yaml
# Regular export options
nas_nfs_export_options:
  - rw
  - sync
  - no_subtree_check

# Root export options (fsid=0)
nas_nfs_root_export_options:
  - rw
  - fsid=0
  - no_subtree_check
  - sync
```

### Samba Configuration

#### Samba User/Group

```yaml
nas_samba_user: smbuser
nas_samba_group: smbgroup
nas_samba_uid: 1036
nas_samba_gid: 1036
nas_samba_user_system: false
nas_samba_group_system: false
```

#### Samba Global Settings

```yaml
nas_samba_workgroup: WORKGROUP
nas_samba_server_string: "Samba Server %v"
nas_samba_netbios_name: "{{ ansible_hostname | upper }}"

# Protocol versions
nas_samba_server_min_protocol: NT1
nas_samba_client_min_protocol: NT1
nas_samba_client_max_protocol: SMB3
nas_samba_ntlm_auth: ntlmv1-permitted

# Network access control
nas_samba_hosts_allow:
  - 127.0.0.1
  - "192.168.41.0/24"

# File/directory permissions
nas_samba_create_mask: "0664"
nas_samba_directory_mask: "2755"
nas_samba_force_create_mode: "0644"
nas_samba_force_directory_mode: "2755"
```

#### Samba Shares

Define Samba shares as a list of dictionaries:

```yaml
nas_samba_shares:
  - name: shared
    path: /srv/samba/shared
    comment: Shared Files
    browseable: true
    public: false
    create_dir: true
    owner: root
    group: "{{ nas_samba_group }}"
    mode: "0775"

  - name: Media
    path: /storage/media
    comment: Media Files
    valid_users:
      - mediauser
      - "@{{ nas_samba_group }}"
    write_list:
      - mediauser
    browseable: true
    public: false
    inherit_permissions: true
```

**Share Parameters**:
- `name` (required): Share name
- `path` (required): Directory path
- `comment` (optional): Share description
- `valid_users` (optional): List of users/groups allowed
- `write_list` (optional): List of users with write access
- `read_only` (optional, default: false): Read-only flag
- `browseable` (optional, default: true): Browseable flag
- `public` (optional, default: false): Guest access
- `create_dir` (optional, default: false): Create directory if missing
- `owner` (optional): Directory owner
- `group` (optional): Directory group
- `mode` (optional): Directory permissions
- `inherit_permissions` (optional, default: true): Inherit parent permissions
- `inherit_acls` (optional, default: false): Inherit ACLs

#### Samba Service Options

```yaml
nas_samba_enable_nmb: true                  # Enable NetBIOS service
nas_samba_enable_client_firewall: false     # Enable samba-client firewall service
nas_samba_enable_homes: true                # Enable [homes] share
nas_samba_disable_printing: true            # Disable printer sharing
```

### Rsync Configuration

#### Rsync Daemon Settings

```yaml
nas_rsync_user: nobody
nas_rsync_group: nobody
nas_rsync_uid: 65534
nas_rsync_gid: 65534

nas_rsync_max_connections: 4
nas_rsync_use_chroot: false
nas_rsync_syslog_facility: local5
```

#### Rsync Modules

Define rsync daemon modules as a list of dictionaries:

```yaml
nas_rsync_modules:
  - name: shared
    path: /srv/rsync/shared
    comment: Shared Files via Rsync
    read_only: false

  - name: backups
    path: /backups
    comment: Backup Storage
    read_only: true
    hosts_allow:
      - "192.168.41.0/24"
```

**Module Parameters**:
- `name` (required): Module name
- `path` (required): Directory path
- `comment` (optional): Module description
- `read_only` (optional, default: false): Read-only flag
- `list` (optional, default: true): Allow listing
- `uid` (optional, defaults to nas_rsync_user): User for file operations
- `gid` (optional, defaults to nas_rsync_group): Group for file operations
- `hosts_allow` (optional): List of allowed hosts/networks
- `hosts_deny` (optional): List of denied hosts/networks

## Dependencies

This role requires the `ansible.posix` collection for firewalld management.

Install with:

```bash
ansible-galaxy collection install ansible.posix
```

## Example Playbook

### Basic Usage

```yaml
---
- name: Configure NAS services
  hosts: nas_servers
  become: true
  roles:
    - role: nas
      vars:
        nas_enable_nfs: true
        nas_enable_samba: true
        nas_enable_rsync: false

        nas_nfs_exports:
          - path: /srv/nfs
            create_dir: true
            is_root: true
          - path: /srv/nfs/data
            create_dir: true

        nas_samba_shares:
          - name: data
            path: /srv/samba/data
            comment: Data Share
            create_dir: true
```

### Advanced Configuration

```yaml
---
- name: Configure NAS with custom settings
  hosts: fileserver
  become: true
  roles:
    - role: nas
      vars:
        # Enable all services
        nas_enable_nfs: true
        nas_enable_samba: true
        nas_enable_rsync: true

        # Custom NFS configuration
        nas_nfs_domain: "example.com"
        nas_nfs_allowed_networks:
          - "192.168.1.0/24"
          - "10.0.0.0/8"

        nas_nfs_exports:
          - path: /export/nfs
            create_dir: true
            is_root: true
          - path: /export/nfs/media
            create_dir: true
            mode: '0775'
          - path: /export/nfs/backups
            create_dir: true
            mode: '0755'
            options:
              - ro
              - sync
              - no_subtree_check

        # Custom Samba configuration
        nas_samba_workgroup: MYWORKGROUP
        nas_samba_hosts_allow:
          - 127.0.0.1
          - "192.168.1.0/24"

        nas_samba_shares:
          - name: public
            path: /srv/samba/public
            comment: Public Share
            public: true
            browseable: true
            create_dir: true
          - name: secure
            path: /srv/samba/secure
            comment: Secure Share
            valid_users:
              - "@smbgroup"
            browseable: false
            create_dir: true

        # Custom Rsync configuration
        nas_rsync_modules:
          - name: backup
            path: /backup
            comment: Backup Module
            read_only: false
            hosts_allow:
              - "192.168.1.0/24"
```

## Directory Structure

After refactoring, the role follows this modular structure:

```
roles/nas/
├── defaults/
│   └── main.yml              # Comprehensive variable definitions
├── vars/
│   ├── Fedora.yml            # Fedora-specific packages
│   └── RedHat.yml            # Rocky/RHEL-specific packages
├── tasks/
│   ├── main.yml              # Main orchestration
│   ├── packages.yml          # Package installation
│   ├── users.yml             # User/group creation
│   ├── nfs/
│   │   ├── main.yml          # NFS orchestration
│   │   ├── config.yml        # Template deployment
│   │   ├── services.yml      # Service management
│   │   ├── firewall.yml      # Firewall rules
│   │   └── exports.yml       # Export management
│   ├── samba/
│   │   ├── main.yml          # Samba orchestration
│   │   ├── config.yml        # Template deployment
│   │   ├── services.yml      # Service management
│   │   └── firewall.yml      # Firewall rules
│   └── rsync/
│       ├── main.yml          # Rsync orchestration
│       └── config.yml        # Template deployment
├── templates/
│   └── etc/
│       ├── exports.j2        # NFS exports
│       ├── idmapd.conf.j2    # NFS ID mapping
│       ├── nfs.conf.j2       # NFS daemon config
│       ├── rsyncd.conf.j2    # Rsync daemon config
│       └── samba/
│           └── smb.conf.j2   # Samba configuration
├── handlers/
│   └── main.yml              # All service handlers
├── meta/
│   └── main.yml              # Role metadata
└── README.md                 # This file
```

## Usage Examples

### NFS-Only Server

```yaml
- hosts: nfs_server
  become: true
  roles:
    - role: nas
      vars:
        nas_enable_nfs: true
        nas_enable_samba: false
        nas_enable_rsync: false
```

### Samba-Only Server

```yaml
- hosts: smb_server
  become: true
  roles:
    - role: nas
      vars:
        nas_enable_nfs: false
        nas_enable_samba: true
        nas_enable_rsync: false
```

### Combined NAS Server

```yaml
- hosts: nas_server
  become: true
  roles:
    - role: nas
      vars:
        nas_enable_nfs: true
        nas_enable_samba: true
        nas_enable_rsync: true
```

## Testing

### Syntax Check

```bash
ansible-playbook playbooks/nas.yml --syntax-check
```

### Dry Run

```bash
ansible-playbook playbooks/nas.yml --check --diff
```

### Run with Tags

```bash
# Install packages only
ansible-playbook playbooks/nas.yml --tags nas_packages

# Configure NFS only
ansible-playbook playbooks/nas.yml --tags nas_nfs

# Configure Samba only
ansible-playbook playbooks/nas.yml --tags nas_samba

# Configure Rsync only
ansible-playbook playbooks/nas.yml --tags nas_rsync
```

### Verify Services

```bash
# Check NFS exports
ansible nas_servers -m shell -a "exportfs -v"

# Check Samba configuration
ansible nas_servers -m shell -a "testparm -s"

# Check running services
ansible nas_servers -m shell -a "systemctl status nfs-server smb nmb rsyncd"
```

## License

MIT

## Author Information

Ansible Workstation Project

---

**Note**: This role has been refactored for RedHat family systems only. For multi-distribution support, please refer to earlier versions of this role or contact the maintainers.
