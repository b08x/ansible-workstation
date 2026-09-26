# b08x.llmops hermes Role

Deploys Hermes Agent as **root** on RHEL-based systems with **Podman** backend and **SELinux enforcing** mode.

## Description

This role installs Hermes Agent (by Nous Research) using the official curl installer, configures Podman as the container runtime backend, sets up a systemd service for persistent operation, and manages SELinux contexts for proper functionality on RHEL 8/9 with SELinux enforcing.

## Requirements

### Platform
- RHEL 8 or 9
- SELinux enforcing (default on RHEL)
- firewalld for firewall management (optional, but recommended)

### Prerequisites
The role handles most dependencies automatically, but requires:
- `git` - for source code access and skill installation
- `curl` - for downloading Node.js archives
- `xz-utils` - for extracting Node.js tar.xz archives
- `podman` (>= 4.0) - container runtime (installed if missing)

## Role Variables

### Container Runtime
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hermes_container_runtime` | str | `podman` | Container runtime: "docker" or "podman" |

### Installation
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hermes_install_user` | str | `root` | User for installation (root for system service) |
| `hermes_install_dir` | str | `/root/.hermes` | Installation directory |
| `hermes_system_service` | bool | `true` | Install as systemd system service |

### Network Configuration
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hermes_gateway_port` | int | `8642` | Gateway API server port |
| `hermes_dashboard_port` | int | `9119` | Dashboard port (loopback by default) |
| `hermes_bind_localhost` | bool | `true` | Bind services to 127.0.0.1 only |
| `hermes_firewall_ports` | list | `["8642/tcp"]` | Ports to open in firewalld |

### SELinux
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hermes_selinux_enforcing` | bool | `true` | Whether SELinux is enforcing |

### Podman
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hermes_podman_version` | str | `"4.0"` | Minimum Podman version |

## Dependencies

None (this role is self-contained and handles all prerequisites).

## Example Playbook

### Basic Usage (Root Install, Podman Backend, System Service)

```yaml
- name: Deploy Hermes Agent on RHEL
  hosts: llmops_servers
  become: true
  roles:
    - role: b08x.llmops.hermes
```

### Custom Configuration

```yaml
- name: Deploy Hermes Agent with custom settings
  hosts: llmops_servers
  become: true
  roles:
    - role: b08x.llmops.hermes
      vars:
        hermes_gateway_port: 9000
        hermes_bind_localhost: false
        hermes_firewall_ports:
          - "9000/tcp"
        hermes_container_runtime: podman
```

### Using include_role

```yaml
- name: Deploy Hermes Agent
  hosts: llmops_servers
  become: true
  tasks:
    - name: Deploy Hermes
      ansible.builtin.include_role:
        name: b08x.llmops.hermes
      vars:
        hermes_system_service: true
        hermes_container_runtime: podman
```

## Installation Process

1. **Prerequisites Check**: Verifies git, curl, xz-utils, and podman are available
2. **Prerequisites Installation**: Installs missing packages via dnf
3. **Hermes Installation**: Runs official curl installer as root
4. **Configuration**: Sets HERMES_DOCKER_BINARY=podman, configures systemd service
5. **SELinux**: Applies proper contexts to installation directory
6. **Service Management**: Installs and starts systemd service
7. **Firewall**: Opens required ports in firewalld (if configured)

## Security Considerations

### Dashboard Access
- The dashboard binds to `127.0.0.1` by default (loopback only)
- **Do NOT expose port 9119 publicly** - it has no built-in authentication
- Access via SSH tunnel or VPN for remote management

### API Server
- Gateway API binds to configurable address/port
- If exposing publicly (not recommended), restrict to trusted IPs
- Consider using authentication and HTTPS

### SELinux
- Installation directory gets proper contexts automatically
- Volume mounts use `:Z` flag for SELinux compatibility

## Data Directories

- **Installation**: `/root/.hermes/hermes-agent/` (for root install)
- **Config**: `/root/.hermes/config.yaml`
- **Secrets**: `/root/.hermes/.env` (API keys - NOT committed to version control)
- **Data**: `/root/.hermes/profiles/` (agent memory, skills, sessions)

## Backup and Restore

Use Hermes CLI for backup operations:
```bash
# Full backup
hermes backup /path/to/backup.dump

# Profile export (excludes credentials)
hermes profile export /path/to/profile.json

# Restore
hermes backup restore /path/to/backup.dump
```

## Testing

### Syntax Check
```bash
ansible-playbook playbooks/site.yml --syntax-check
```

### Idempotency
The role is designed to be idempotent. Running it multiple times should not cause changes after the first successful run.

## Role Idempotency

**True** - This role is fully idempotent. It checks for existing installations and only makes changes when necessary.

## Role Atomicity

**False** - This role is not atomic. It consists of multiple steps (installation, configuration, service setup) that can be run independently.

## Roll-back capabilities

**Manual** - Roll back by:
1. Stopping and disabling the hermes-gateway service
2. Removing the installation directory (`/root/.hermes`)
3. Removing the systemd unit file
4. Removing installed prerequisites (optional)

```bash
# Stop service
sudo systemctl stop hermes-gateway
sudo systemctl disable hermes-gateway

# Remove installation
sudo rm -rf /root/.hermes

# Remove systemd unit
sudo rm /etc/systemd/system/hermes-gateway.service
sudo systemctl daemon-reload
```

## Argument Specification

See `meta/argument_specs.yml` for full validation rules.

## License

GPL-2.0-or-later

## Author Information

b08x (Robert Pannick) - rwpannick@gmail.com

## References

- [Hermes Agent Official Documentation](https://hermes-agent.nousresearch.com/)
- [Hermes Agent GitHub](https://github.com/nousresearch/hermes-agent)
- [Track: Role: hermes (llmops)](track-role-hermes-llmops-1kzjfxq)
- [Research: hermes-requirements.md](tracks/track-role-hermes-llmops-1kzjfxq/files/hermes-requirements.md)
