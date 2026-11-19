# Ansible Role: tools

Provisions host-level graphical desktop utilities — Visual Studio Code (real opt-in), system management Flatpaks, and hardware key remapping (`input-remapper`) — across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

Coding agent CLIs are provisioned by the standalone playbooks in [`playbooks/agent-harness/`](../../playbooks/agent-harness/). transcribe.cpp (Whisper transcription CLI) is built by the standalone [`playbooks/transcribe-cpp.yml`](../../playbooks/transcribe-cpp.yml) playbook.

**Migration note (2026-11):** this role divested its CLI toolchain surface.
`inxi` and `gitflow-avh` moved to [`roles/common`](../common); `bun`, the Go toolchain, cargo/crates, GNOME Shell extensions, and VS Code extensions moved to [`roles/user`](../user). Homebrew support was dropped entirely. VS Code itself is now a **real opt-in** (`tools_vscode_install_method` defaults to `"none"`).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `tools` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy system packages, desktop applications, and hardware services.

It establishes a strict boundary separating binary installation from user configuration: Ansible installs host-level desktop applications and services, while **Layer 2 (Yadm)** manages user dotfiles, API keys, agent skills, and personal application configuration files.

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Configuration Files: dotfiles, ~/.zshenv, ~/.cargo/                    |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/tools (Ansible)                      |
|   - Developer IDEs & Graphical Tools (gated by tools_install_gui_apps): |
|       * Visual Studio Code (Native DNF RPM or Flatpak, opt-in)           |
|       * System-scoped Flatpaks & Flathub Remote                          |
|       * Hardware Key Remapping Service (input-remapper daemon)           |
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

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular installers (`vscode.yml`, `flatpak.yml`, `input-remapper.yml`) gated by explicit boolean feature flags (`tools_install_*`).
2. **GUI Availability Gating**: Graphical desktop tools (VS Code, system Flatpaks, input-remapper) are gated on `tools_install_gui_apps: "{{ auto_enable_desktop | default((desktop_environment | default('none')) != 'none') | bool }}"`. Headless systems automatically skip graphical installations.
3. **Real Opt-In Flip**: VS Code installs only when BOTH `tools_install_gui_apps` is true AND `tools_vscode_install_method` is `'rpm'` or `'flatpak'`; the latter defaults to `'none'` so the IDE is a deliberate choice, never a side effect.
4. **Idempotency Stat Guards & Check-Mode Safety**: Every installer performs a preliminary stat check or binary probe to bypass redundant work on converged hosts. Probe commands (`which code`) declare `check_mode: false` and defensive filters (`rc | default(1)`).
5. **Handler Notification Pattern**: Changes to service unit files (`input-remapper.service`) notify `Daemon reload` (`systemd daemon_reload: true`).
6. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`tools`, `system`) and dedicated tool tags (`vscode`, `flathub`, `flatpaks`, `input-remapper`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `user.home`) and Tier 2 namespaced role variables (`tools_*`).
8. **Pre-flight Assertion Pattern**: Frontloads prerequisite validation (`tasks/assert.yml`) to fail fast when prerequisites (OS family, effective root privileges) are missing or misconfigured.

---

## Core Components

### 1. Visual Studio Code (`tasks/vscode.yml`) — opt-in
- Installs only when `tools_vscode_install_method` is `'rpm'` or `'flatpak'` (default `'none'`) AND `tools_install_gui_apps` is true.
- Configures Microsoft's official yum repository and GPG signing key (`https://packages.microsoft.com/keys/microsoft.asc`) when `tools_vscode_install_method == 'rpm'`.
- Supports native RPM installation (`tools_vscode_install_method: "rpm"`) or Flatpak distribution (`tools_vscode_install_method: "flatpak"`).
- The extension list is **not** managed here — [`roles/user`](../user) installs extensions (`user_vscode_extensions`, gate `user_install_vscode_extensions`).

### 2. System Flatpaks & Flathub Remote (`tasks/flatpak.yml`)
- Configures the official Flathub remote repository (`https://dl.flathub.org/repo/flathub.flatpakrepo`) under system scope (`method: system`).
- Deploys administrative, utility, and creative Flatpak applications defined in `tools_system_flatpaks`.
- Gated by `tools_install_gui_apps` and `tools_install_flatpaks`.

### 3. Hardware Key Remapper (`tasks/input-remapper.yml`)
- Checks `/usr/bin/input-remapper-gtk` via `ansible.builtin.stat` for idempotency.
- **Fedora**: Installs the native `input-remapper` RPM package via DNF.
- **Enterprise Linux (AlmaLinux & Rocky Linux)**: Installs required Python dependencies (`evdev`, `pydantic`, `dasbus`, `PyGObject`, `psutil`), clones the upstream repository, and installs the service using Python installer hooks.
- Enables and starts the `input-remapper` systemd service.
- Gated by `tools_install_gui_apps` and `tools_install_input_remapper`.

### Divested tooling (new owners)

| Former `tools` feature | New owner |
|---|---|
| `inxi` | [`roles/common`](../common) (`common_install_inxi`) |
| `gitflow-avh` | [`roles/common`](../common) (`common_install_gitflow`) |
| `bun` (now `~/.bun/bin`, user-space) | [`roles/user`](../user) (`user_install_bun`) |
| Go toolchain (system-first, user-space fallback) | [`roles/user`](../user) (`user_install_go`) |
| cargo/crates | [`roles/user`](../user) (`user_install_cargo`) |
| GNOME Shell user extensions | [`roles/user`](../user) (`user_install_gnome_extensions`) |
| VS Code extensions | [`roles/user`](../user) (`user_install_vscode_extensions`) |
| Homebrew | **Dropped** (no owner) |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

| Variable | Default | Description |
|---|---|---|
| `auto_enable_desktop` | *(derived)* | Capability flag evaluated during `local.yml` preflight checks; feeds `tools_install_gui_apps`. |
| `desktop_environment` | `"none"` | Active desktop environment; used to derive `tools_install_gui_apps` when `auto_enable_desktop` is undefined. |

### Tier 2: Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `tools_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`). |
| `tools_install_gui_apps` | `{{ auto_enable_desktop \| default((desktop_environment \| default('none')) != 'none') \| bool }}` | Master gate for graphical desktop applications. |
| `tools_vscode_install_method` | `"none"` | Visual Studio Code installation method (`"none"`, `"rpm"`, or `"flatpak"`). |
| `tools_vscode_force_install` | `false` | When true, forces installation even if `code` binary is present. |
| `tools_install_flatpaks` | `{{ tools_install_gui_apps \| default(false) \| bool }}` | Enable/disable Flatpak package and system Flatpaks. |
| `tools_system_flatpaks` | *(17 packages)* | System Flatpak application IDs to install. |
| `tools_install_input_remapper` | `{{ tools_install_gui_apps \| default(false) \| bool }}` | Enable/disable input-remapper service configuration. |

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
