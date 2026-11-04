# Ansible Role: tools

Provisions host-level command-line utilities, Go toolchain environment validation (>= 1.22), the Visual Studio Code developer IDE, system management Flatpaks, and hardware key remapping (`input-remapper`) across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

Coding agent CLIs are provisioned by the standalone playbooks in [`playbooks/agent-harness/`](../../playbooks/agent-harness/). transcribe.cpp (Whisper transcription CLI) is built by the standalone [`playbooks/transcribe-cpp.yml`](../../playbooks/transcribe-cpp.yml) playbook.

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `tools` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy root-owned system binaries (`/usr/local/bin`), developer IDEs, hardware services, and user-scoped executable tools (`~/.local/bin`).

It establishes a strict boundary separating binary installation from user configuration: Ansible installs executable toolchains and system-level desktop applications, while **Layer 2 (Yadm)** manages user dotfiles, API keys, agent skills, and personal application configuration files.

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Configuration Files & Shared Agent Skills:                             |
|   ~/.gemini/skills/                                                       |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/tools (Ansible)                      |
|   - System Binaries (/usr/local/bin):                                    |
|       * Bun Standalone JS/TS Runtime (bun)                               |
|   - Developer IDEs & Graphical Tools (gated by tools_install_gui_apps):  |
|       * Visual Studio Code (Native DNF RPM or Flatpak)                   |
|       * System-scoped Flatpaks & Flathub Remote                          |
|       * Hardware Key Remapping Service (input-remapper daemon)           |
|   - User Toolchains (~/.local/bin & ~/go/bin):                           |
|       * Go Compiler Validation (>= 1.22 in PATH)                         |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|        Hardware Acceleration: see the `gpu` role (NVIDIA CUDA,           |
|        Intel oneAPI/graphics)                                            |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular tool installers (`runtimes.yml`, `bun.yml`, `go.yml`, `gitflow.yml`, `inxi.yml`, `homebrew.yml`, `vscode.yml`, `flatpak.yml`, `input-remapper.yml`) gated by explicit boolean feature flags (`tools_install_*`).
2. **GUI Availability Gating**: Graphical desktop tools (VS Code, system Flatpaks, input-remapper) are gated on `tools_install_gui_apps: "{{ auto_enable_desktop | default(true) | bool }}"`. Headless systems automatically skip graphical installations while retaining all CLI utilities.
3. **Idempotency Stat Guards & Check-Mode Safety**: Every installer performs a preliminary stat check or version probe (`bun`, `go`, `vscode`, `input-remapper`) to bypass redundant archive downloads, git checkouts, and compilations on converged hosts. Probe commands (`which go`, `go version`, `which code`) declare `check_mode: false` and defensive filters (`rc | default(1)`).
4. **User Context & Runtime Isolation (`become_user`)**: User-scoped tools and Go-compiled utilities install strictly under `become_user: "{{ tools_user }}"`, preserving unprivileged home directory ownership.
5. **Handler Notification Pattern**: Changes to service unit files (`input-remapper.service`) notify `Daemon reload` (`systemd daemon_reload: true`).
6. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`tools`, `system`) and dedicated tool tags (`bun`, `go`, `vscode`, `flathub`, `flatpaks`, `input-remapper`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `user.home`) and Tier 2 namespaced role variables (`tools_*`).
8. **Pre-flight Assertion Pattern**: Frontloads prerequisite validation (`tasks/assert.yml`) to fail fast when prerequisites (OS family, effective root privileges, target user configuration, Go toolchain parameters) are missing or misconfigured.

---

## Core Components & Toolchains

### 1. Bun JavaScript / TypeScript Runtime (`tasks/bun.yml`)
- Deploys the official standalone [Bun](https://bun.sh/) executable to `/usr/local/bin/bun`.
- Architecture-aware download for `x86_64` and `aarch64`.
- Idempotently checks binary existence and permissions before initiating downloads.

### 2. Go Toolchain Environment Validation (`tasks/go.yml`)
- Verifies that a valid Go compiler (>= 1.22, controlled by `tools_go_min_version`) is available in `PATH`.
- Prepares user binary and Go workspace directories (`~/.local/bin` and `~/go/bin`) under target user ownership.
- Probes compiler availability and version using `which go` and `go version` with check-mode safe flags.
- Asserts environment readiness via `ansible.builtin.assert`, failing fast with guidance to install Go via package manager (e.g. `dnf install golang`) if Go is absent or below the required version.

### 3. Visual Studio Code (`tasks/vscode.yml`)
- Checks for existing `code` binary in `$PATH` to ensure idempotency.
- Configures Microsoft's official yum repository and GPG signing key (`https://packages.microsoft.com/keys/microsoft.asc`).
- Supports native RPM installation (default) or Flatpak distribution (`tools_vscode_flatpak: true`).
- Gated by `tools_install_gui_apps` and `tools_install_vscode`.

### 4. System Flatpaks & Flathub Remote (`tasks/flatpak.yml`)
- Configures the official Flathub remote repository (`https://dl.flathub.org/repo/flathub.flatpakrepo`) under system scope (`method: system`).
- Deploys administrative, utility, and creative Flatpak applications defined in `tools_system_flatpaks` (overridable via `system_flatpaks`).
- Gated by `tools_install_gui_apps` and `tools_install_flatpaks`.

### 5. Hardware Key Remapper (`tasks/input-remapper.yml`)
- Checks `/usr/bin/input-remapper-gtk` via `ansible.builtin.stat` for idempotency.
- **Fedora**: Installs the native `input-remapper` RPM package via DNF.
- **Enterprise Linux (AlmaLinux & Rocky Linux)**: Installs required Python dependencies (`evdev`, `pydantic`, `dasbus`, `PyGObject`, `psutil`), clones the upstream repository, and installs the service using Python installer hooks.
- Enables and starts the `input-remapper` systemd service.
- Gated by `tools_install_gui_apps` and `tools_install_input_remapper`.

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT). |
| `user.home` | `"/home/" ~ user.name` | Home directory of primary workstation user. |
| `auto_enable_desktop` | `true` | Capability flag evaluated during `local.yml` preflight checks. |
| `system_flatpaks` | *(undefined)* | Optional global override for the system Flatpak list. |

### Tier 2: Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `tools_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`). |
| `tools_user` | `{{ user.name }}` | Target workstation user for user-scoped tools. |
| `tools_user_home` | `{{ user.home }}` | Home directory of target user. |
| `tools_user_local_bin` | `{{ tools_user_home }}/.local/bin` | User binary execution directory. |
| `tools_user_go_bin` | `{{ tools_user_home }}/go/bin` | User Go binary execution directory. |
| `tools_install_runtimes` | `true` | Install developer toolchains and language runtimes (golang, nodejs, npm). |
| `tools_install_bun` | `true` | Enable/disable Bun installation. |
| `tools_install_go` | `true` | Enable/disable Go toolchain environment validation. |
| `tools_go_min_version` | `"1.22"` | Minimum Go compiler version required in PATH. |
| `tools_install_gui_apps` | `{{ auto_enable_desktop \| default(true) \| bool }}` | Master gate for graphical desktop applications. |
| `tools_install_vscode` | `{{ tools_install_gui_apps }}` | Enable/disable Visual Studio Code installation. |
| `tools_vscode_flatpak` | `false` | When true, installs VS Code via Flatpak instead of native RPM. |
| `tools_vscode_force_install` | `false` | When true, forces installation even if `code` binary is present. |
| `tools_install_flatpaks` | `{{ tools_install_gui_apps }}` | Enable/disable Flatpak package and system Flatpaks. |
| `tools_system_flatpaks` | *(19 packages)* | System Flatpak application IDs to install. |
| `tools_install_input_remapper` | `{{ tools_install_gui_apps }}` | Enable/disable input-remapper service configuration. |

---

## Handlers

| Handler Name | Description |
|---|---|
| `Daemon reload` | Reloads systemd manager configuration (`systemd daemon_reload: true`) when unit files are created or updated by input-remapper. |

---

## Tags

| Tag | Scope | Description |
|---|---|---|
| `tools` | Role | Applies to all tasks within the `tools` role. |
| `assert` | Validation | Executes pre-flight assertion tasks. |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `bun` | Feature | Runs only Bun installation tasks. |
| `go` | Feature | Runs only Go toolchain environment validation tasks. |
| `vscode` | Feature | Runs only Visual Studio Code installation tasks. |
| `flathub` | Feature | Ensures system Flathub remote repository is configured. |
| `flatpaks` | Feature | Deploys system Flatpak applications. |
| `input-remapper` | Feature | Builds and configures input-remapper systemd daemon. |
| `always` | System | Preamble debug logging. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks (`playbooks/workstation.yml`)

```yaml
- name: Host Tools
  hosts: workstations
  become: true
  roles:
    - role: tools
      tags: ["tools", "system"]
```

### 2. Autonomous Local Provisioning (`local.yml`)

```yaml
    - name: Execute tools role
      ansible.builtin.include_role:
        name: tools
      tags: ["tools", "system", "assert"]
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/tools
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
