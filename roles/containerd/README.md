# Ansible Role: containerd

Container runtime engine orchestration and developer environment provisioning for workstation fleets across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

In the [workstation layering taxonomy](../../docs/layering-architecture.md), the `containerd` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy and configure the container runtimes that power the **Fast Layer (Containers & AI/LLM Workloads)**.

While the host operating system maintains an immutable or slow-moving, predictable baseline, container runtimes isolate fast-moving, high-churn applications—such as language model harnesses, autonomous agent runtimes, RAG pipelines, and ephemeral guest development environments—completely away from the host ABI.

```
+--------------------------------------------------------------------------+
|                        Fast Layer (Containers & LLMs)                    |
|       Language Models, Agent Harnesses, RAG, Ephemeral Dev Stacks        |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Layer 1: roles/containerd (Ansible)                   |
|   - Podman Engine + Compose + Docker CLI Shim (Default)                  |
|   - Distrobox Host-Integrated Guest Environments                         |
|   - Docker Community Edition Engine & Plugins (Optional)                 |
|   - Kernel Storage & Overlay Tuning (/etc/modprobe.d)                    |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Kernel                 |
|            Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                  |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` serves as the primary dispatcher routing execution conditionally to `podman.yml` and `docker.yml` based on explicit feature flags (`containerd_use_podman` and `containerd_use_docker`).
2. **Distro-Switching Pattern (Dialect A)**: Dynamic OS-specific variable inclusion via `vars/{{ ansible_distribution }}.yml`, cleanly supporting Fedora, AlmaLinux, and Rocky Linux without cluttered inline conditional logic.
3. **Failure-Shape Pattern (Shape 1: Context Re-raise)**: The `distrobox` installation block catches task failures in a `rescue` clause, emits actionable diagnostic guidance regarding EPEL repository requirements on Enterprise Linux, and cleanly re-raises the failure via `ansible.builtin.fail`.
4. **Tag-as-Select Pattern**: Every task and include is tagged with domain tags (`containerd`, `virt`) and fine-grained feature tags (`podman`, `docker`, `distrobox`, `packages`) for selective execution.
5. **Backup-on-Write Pattern**: All templated and altered configuration files (`/etc/docker/daemon.json`, `/usr/lib/systemd/system/docker.service`, `/etc/modprobe.d/disable-overlay-redirect-dir.conf`) set `backup: true` to protect manual configurations.
6. **Handler Notification Pattern**: Changes to Docker configuration or systemd service configurations trigger standard handler notifications (`Restart Docker` and `Reload systemd`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`) and Tier 2 role-namespaced variables (`containerd_*`).
8. **Fail-Fast Precondition Assertions (`tasks/assert.yml`)**: Pre-flight validation executed at role entry (`containerd_assert_enabled`) asserting RedHat OS family support, DNF package manager availability, effective root privileges (`id -u == 0`), and target user identity definition when Docker group management is active. Also available for standalone invocation via `tasks_from: assert.yml`.

---

## Container Engines & Components

### 1. Podman (Default Container Engine)

**Enabled by default** (`containerd_use_podman: true`).

Podman is the first-class container runtime across modern Fedora and Enterprise Linux systems:
- **Daemonless & Rootless**: Containers run without a root-owned background daemon by default, leveraging Linux user namespaces and cgroups v2 for enhanced security and resource isolation.
- **Docker CLI Compatibility**: Installs `podman-docker` to provide an alias/shim for `docker` commands, allowing existing Docker workflows, scripts, and developer tools to function transparently.
- **Compose Support**: Installs `podman-compose` for declarative multi-container orchestration.
- **Systemd Integration**: Rootless containers natively integrate with unprivileged systemd user units (`systemd --user`).

### 2. Docker Community Edition (Optional Engine)

**Disabled by default** (`containerd_use_docker: false`).

For workflows requiring the native Moby/Docker daemon:
- **Dynamic Repository Configuration**: Ingests Docker's official GPG signing key (`containerd_docker_gpg_key_url`) and establishes the appropriate stable yum repository based on `containerd_docker_repo_os` (`fedora`, `alma`, or `rocky`).
- **Distribution-Specific Packaging**: Deploys `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`, and `docker-model-plugin`. On Fedora, installs the complete engine stack (`docker-ce`, `docker-ce-cli`, `docker-ce-rootless-extras`).
- **Daemon Configuration**: Templates `/etc/docker/daemon.json` from the `containerd_docker_daemon_config` dictionary.
- **Storage Redirection**: Supports relocating Docker's root data directory via `--data-root` in systemd unit definitions (`containerd_docker_storage`).
- **OverlayFS Tuning**: Configures `/etc/modprobe.d/disable-overlay-redirect-dir.conf` (`options overlay metacopy=off redirect_dir=off`) to avoid filesystem corruption and redirection issues across layered filesystems.
- **User Group Management**: Automatically grants non-root Docker socket access by appending `containerd_docker_users` (defaults to `{{ user.name }}`) to the `docker` system group.

### 3. Distrobox

**Installed by default**:
- Distrobox enables running arbitrary Linux distribution container images (Arch, Ubuntu, Debian, Alpine) directly integrated into the workstation host's terminal, user home directory, Wayland/X11 sockets, and audio servers.
- Automatically installed via DNF. On Enterprise Linux distributions (AlmaLinux and Rocky Linux), Distrobox packages are sourced from EPEL (managed by `roles/base`).

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Distro Variable File** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky.yml` |
| **Default Container Engine** | Podman (rootless) | Podman (rootless) | Podman (rootless) |
| **Podman Packages** | `podman`, `podman-compose`, `podman-docker` | `podman`, `podman-compose`, `podman-docker` | `podman`, `podman-compose`, `podman-docker` |
| **Docker CE Repo OS Slug** | `fedora` | `alma` | `rocky` |
| **Docker CE Distro Packages** | `docker-ce`, `docker-ce-cli`, `docker-ce-rootless-extras` | *None* (Plugins only upstream) | *None* (Plugins only upstream) |
| **Docker Daemon Management** | Enabled (`docker.service`) | Disabled (Podman preferred) | Disabled (Podman preferred) |
| **Distrobox Source** | Fedora Core Repositories | EPEL (via `roles/base`) | EPEL (via `roles/base`) |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT). |
| `auto_enable_containerd` | `true` | Capability flag evaluated during `local.yml` pre-flight checks to determine whether to include the container role. |
| `pull_enable_containerd` | *(undefined)* | Optional manual override in `local.yml` to force-enable or disable container runtime provisioning. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `containerd_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `containerd_assert_enabled` | `true` | Enable pre-flight environment, platform, and privilege assertions. |
| `containerd_use_podman` | `true` | Enable Podman runtime and related CLI packages. |
| `containerd_use_docker` | `false` | Enable Docker Community Edition engine and repository configuration. |
| `containerd_podman_packages` | `["podman", "podman-compose", "podman-docker"]` | List of Podman packages installed on the host. |
| `containerd_docker_version` | `""` | Optional specific Docker CE version string to pin (e.g. `"27.3.1"`). |
| `containerd_docker_packages` | `["containerd.io", "docker-buildx-plugin", "docker-compose-plugin", "docker-model-plugin"]` | Core Docker packages installed across all platforms. |
| `containerd_docker_gpg_key_url` | `"https://download.docker.com/linux/fedora/gpg"` | GPG key URL used to sign official Docker CE packages. |
| `containerd_docker_service_name` | `"docker.service"` | Name of the systemd unit for the Docker daemon. |
| `containerd_docker_service_enabled` | `true` | Whether to enable and start the Docker systemd service (overridden by distro vars). |
| `containerd_docker_users` | `["{{ user.name }}"]` | List of user accounts added to the `docker` system group. |
| `containerd_docker_storage` | `"/var/lib/docker"` | Custom data root directory path for the Docker daemon (`--data-root`). |
| `containerd_docker_daemon_config` | `{}` | Key-value mapping rendered into `/etc/docker/daemon.json`. |
| `containerd_docker_remove_conflicting_packages` | `false` | Gate to uninstall conflicting container packages if necessary. |

### Tier 2: Distribution Variables (`vars/*.yml`)

These variables are dynamically included based on `{{ ansible_distribution }}.yml`:

| Variable | Fedora | AlmaLinux | Rocky Linux | Description |
|---|---|---|---|---|
| `containerd_docker_distro_packages` | `[docker-ce, docker-ce-cli, docker-ce-rootless-extras]` | `[]` | `[]` | Additional distribution-specific packages for Docker CE. |
| `containerd_docker_repo_os` | `"fedora"` | `"alma"` | `"rocky"` | Docker repository slug in `download.docker.com/linux/<repo_os>/`. |
| `containerd_docker_service_enabled` | `true` | `false` | `false` | Distribution default for starting the Docker daemon. |
| `containerd_docker_manage_users` | `true` | `false` | `false` | Whether to manage `docker` group membership. |
| `containerd_docker_manage_storage` | `true` | `false` | `false` | Whether to override `--data-root` in systemd service definitions. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `containerd` | Role | Applies to all tasks within the `containerd` role. |
| `virt` | Playbook | Tag grouping container and virtualization roles (`containerd`, `libvirt`). |
| `podman` | Feature | Executes Podman package installation and rootless configuration checks. |
| `docker` | Feature | Executes Docker repository setup, package installation, user group, daemon config, and service management. |
| `distrobox` | Feature | Executes Distrobox installation and failure-handling rescue blocks. |
| `packages` | Feature | Targets package installation tasks across runtimes. |
| `always` | System | Role preamble and `include_vars` for OS-specific variable loading. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included within `playbooks/workstation.yml` as part of the system provisioning stage:

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

In `local.yml`, hardware preflight checks detect container requirements and gate execution:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: containerd
      when: auto_enable_containerd | default(true) | bool
      tags: ["containerd", "virt"]
```

### 3. Execution Commands

Run only the container role during a workstation convergence:

```bash
ansible-playbook playbooks/workstation.yml --tags "containerd"
```

Provision Podman and Distrobox without Docker:

```bash
ansible-playbook local.yml --tags "podman,distrobox"
```

Enable Docker CE explicitly via extra variables:

```bash
ansible-playbook local.yml --tags "containerd" -e "containerd_use_docker=true"
```

---

## Verification & Health Checks

After role convergence, verify container runtime health using standard CLI commands:

### Podman & Compose Verification

```bash
# Verify Podman engine and rootless configuration
podman info

# Run a test rootless container
podman run --rm alpine uname -a

# Verify compose and docker compatibility
podman-compose --version
docker --version
```

### Distrobox Verification

```bash
# Verify Distrobox installation
distrobox --version

# Create and enter an ephemeral test container
distrobox create --name test-box --image alpine:latest -Y
distrobox enter test-box -- echo "Distrobox working correctly"
distrobox rm -f test-box
```

### Docker Verification (when `containerd_use_docker: true`)

```bash
# Check Docker daemon service state
systemctl status docker.service

# Verify Docker socket permissions as workstation user
docker info
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/containerd
```

Execute role unit testing via the provided test play:

```bash
ansible-playbook roles/containerd/tests/test.yml -i roles/containerd/tests/inventory --check
```

---

## License

MIT

## Author Information

Syncopated Workstation Team
