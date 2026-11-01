# Ansible Role: tools

Provisions host-level command-line utilities, hardware-accelerated compiled binaries, Go toolchain environment validation (>= 1.22), AI coding agent command-line interfaces (`agy`, `claude`, `crush`, `opencode`), developer IDEs (Visual Studio Code, Google Antigravity Hub & IDE), system management Flatpaks, and hardware key remapping (`input-remapper`) across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `tools` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy root-owned system binaries (`/usr/local/bin`), developer IDEs, hardware services, and user-scoped executable tools (`~/.local/bin`).

It establishes a strict boundary separating binary installation from user configuration: Ansible installs executable toolchains, agent binaries, and system-level desktop applications, while **Layer 2 (Yadm)** manages user dotfiles, API keys, agent skills, and personal application configuration files.

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Configuration Files & Shared Agent Skills:                             |
|   ~/.gemini/antigravity-cli/settings.json, ~/.claude/settings.json,      |
|   ~/.config/crush/crushrc, ~/.config/opencode/,                          |
|   ~/.gemini/skills/                                                      |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/tools (Ansible)                      |
|   - System Binaries & Hardware CLI Tools (/usr/local/bin):               |
|       * Bun Standalone JS/TS Runtime (bun)                               |
|       * Hardware-Accelerated Audio Transcription (transcribe.cpp)        |
|   - Developer IDEs & Graphical Tools (gated by tools_install_gui_apps):  |
|       * Visual Studio Code (Native DNF RPM or Flatpak)                   |
|       * Google Antigravity Hub & IDE (/opt binaries & desktop entries)   |
|       * System-scoped Flatpaks & Flathub Remote                          |
|       * Hardware Key Remapping Service (input-remapper daemon)           |
|   - User Toolchains & Coding Agent CLIs (~/.local/bin & ~/go/bin):       |
|       * Go Compiler Validation (>= 1.22 in PATH)                         |
|       * Google Antigravity CLI (agy)                                     |
|       * Anthropic Claude Code CLI (claude)                               |
|       * Charm Crush CLI (Go-compiled in ~/go/bin and ~/.local/bin)       |
|       * OpenCode CLI (opencode)                                          |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|            Hardware Acceleration: NVIDIA CUDA, Intel oneAPI/Vulkan       |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular tool installers (`bun.yml`, `transcribe-cpp.yml`, `go.yml`, `antigravity.yml`, `claude.yml`, `crush.yml`, `opencode.yml`, `intel.yml`, `gitflow.yml`, `inxi.yml`, `homebrew.yml`, `vscode.yml`, `flatpak.yml`, `input-remapper.yml`) gated by explicit boolean feature flags (`tools_install_*`).
2. **GUI Availability Gating**: Graphical desktop tools (VS Code, Antigravity Hub & IDE, system Flatpaks, input-remapper) are gated on `tools_install_gui_apps: "{{ auto_enable_desktop | default(true) | bool }}"`. Headless systems automatically skip graphical installations while retaining all CLI utilities.
3. **Pre-flight Hardware Capability Checks**:
   - `tasks/transcribe-cpp.yml` probes the host for CUDA hardware devices (`nvidia-smi`, `/dev/nvidia*`, PCI vendor `0x10de`) and Vulkan physical GPU devices (`vulkaninfo`, render nodes).
   - If neither CUDA nor Vulkan hardware devices are present and `tools_transcribe_require_gpu: true`, compilation is automatically **skipped** with an informative debug notice rather than failing or wasting resources on CPU builds.
4. **Failure-Shape Pattern (Shape 2: True Fallback & Auto-Detection)**:
   - Evaluates hardware acceleration tiers for Whisper transcription: CUDA (`GGML_CUDA=ON`) &rarr; Intel SYCL/oneAPI (`GGML_SYCL=ON`) &rarr; Vulkan (`GGML_VULKAN=ON`) &rarr; CPU fallback.
5. **Idempotency Stat Guards & Check-Mode Safety**: Every installer performs a preliminary stat check or version probe (`bun`, `transcribe`, `agy`, `claude`, `crush`, `opencode`, `vscode`, `input-remapper`) to bypass redundant archive downloads, git checkouts, and compilations on converged hosts. Probe commands (`which npm`, `which uv`, `which go`, `go version`, `which code`) declare `check_mode: false` and defensive filters (`rc | default(1)`).
6. **User Context & Runtime Isolation (`become_user`)**: User-scoped tools and Go-compiled utilities install strictly under `become_user: "{{ tools_user }}"`, preserving unprivileged home directory ownership. Additionally, npm global installs (`claude`, `opencode`) define `TMPDIR: "/run/user/{{ user.uid }}/tmp"` under unprivileged `become_user` to eliminate tempfile permission collisions.
7. **Handler Notification Pattern**: Changes to service unit files (`input-remapper.service`) notify `Daemon reload` (`systemd daemon_reload: true`).
8. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`tools`, `agents`, `system`) and dedicated tool tags (`bun`, `transcribe`, `go`, `antigravity`, `claude`, `crush`, `opencode`, `vscode`, `flathub`, `flatpaks`, `input-remapper`).
9. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `user.home`) and Tier 2 namespaced role variables (`tools_*`).
10. **Pre-flight Assertion Pattern**: Frontloads prerequisite validation (`tasks/assert.yml`) to fail fast when prerequisites (OS family, effective root privileges, target user configuration, Go toolchain parameters) are missing or misconfigured.

---

## Core Components & Toolchains

### 1. Bun JavaScript / TypeScript Runtime (`tasks/bun.yml`)
- Deploys the official standalone [Bun](https://bun.sh/) executable to `/usr/local/bin/bun`.
- Architecture-aware download for `x86_64` and `aarch64`.
- Idempotently checks binary existence and permissions before initiating downloads.

### 2. Transcribe.cpp Whisper Engine (`tasks/transcribe-cpp.yml`)
- Clones and builds [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) (Whisper audio transcription CLI) with automatic hardware acceleration detection:
  - **Hardware Qualification Gate**: Controlled by `tools_transcribe_require_min_specs: true` (default). Verifies host meets minimum hardware requirements of 16 CPU cores/vCPUs and 32 GB RAM before attempting compilation.
  - **CUDA (NVIDIA)**: Probes hardware device and `command -v nvcc` &rarr; compiles with `-DGGML_CUDA=ON -DTRANSCRIBE_CUDA=ON`.
  - **Intel oneAPI / SYCL**: Probes `icpx`/`dpcpp`/`icx` (sourcing `setvars.sh`) &rarr; compiles with `-DGGML_SYCL=ON -DCMAKE_CXX_COMPILER=<probed compiler>` inside the oneAPI environment.
  - **Vulkan**: Probes Vulkan physical GPUs (Intel Iris/Arc, AMD Radeon, NVIDIA) &rarr; compiles with `-DGGML_VULKAN=ON -DTRANSCRIBE_VULKAN=ON`.
  - **GPU Requirement Gate**: Controlled by `tools_transcribe_require_gpu: true` (default). When no GPU accelerator is found, cleanly skips compilation.
- Installs binary to `/usr/local/bin/transcribe`.

### 3. Go Toolchain Environment Validation (`tasks/go.yml`)
- Verifies that a valid Go compiler (>= 1.22, controlled by `tools_go_min_version`) is available in `PATH`.
- Prepares user binary and Go workspace directories (`~/.local/bin` and `~/go/bin`) under target user ownership.
- Probes compiler availability and version using `which go` and `go version` with check-mode safe flags.
- Asserts environment readiness via `ansible.builtin.assert`, failing fast with guidance to install Go via package manager (e.g. `dnf install golang`) if Go is absent or below the required version.

### 4. Google Antigravity Suite (`tasks/antigravity.yml`)
- **CLI (`agy`)**: Installs the official Google Antigravity CLI into `~/.local/bin/agy` for the target user.
- **Hub & IDE (GUI)**: Deploys the Antigravity Hub (`/opt/antigravity`) and IDE (`/opt/antigravity-ide`) tarballs to system directories, verified by `.installed_url` checksum markers. Generates standard Freedesktop `.desktop` application launchers. Gated by `tools_install_gui_apps` and `tools_install_antigravity_gui`.

### 5. Anthropic Claude Code CLI (`tasks/claude.yml`)
- Installs Anthropic's Claude Code CLI (`@anthropic-ai/claude-code`) via user npm global prefix into `~/.local/bin/claude`.
- Applies `TMPDIR: "/run/user/{{ user.uid }}/tmp"` runtime isolation under unprivileged `become_user` to eliminate tempfile permission collisions during npm global installation.

### 6. Charm Crush CLI (`tasks/crush.yml`)
- Compiles Charm's Crush CLI (`github.com/charmbracelet/crush@latest`) using Go (`go install`).
- Installs binary to `~/go/bin/crush` and symlinks into `~/.local/bin/crush`.
- Sets `GOTOOLCHAIN: "auto"` parameter in the build environment to ensure smooth compilation when dependencies require newer toolchains than host default.

### 7. OpenCode CLI (`tasks/opencode.yml`)
- Installs OpenCode (`opencode-ai`) via user npm global prefix into `~/.local/bin/opencode`.
- Implements `TMPDIR: "/run/user/{{ user.uid }}/tmp"` runtime isolation under unprivileged `become_user` to eliminate tempfile permission collisions.

### 8. Visual Studio Code (`tasks/vscode.yml`)
- Checks for existing `code` binary in `$PATH` to ensure idempotency.
- Configures Microsoft's official yum repository and GPG signing key (`https://packages.microsoft.com/keys/microsoft.asc`).
- Supports native RPM installation (default) or Flatpak distribution (`tools_vscode_flatpak: true`).
- Gated by `tools_install_gui_apps` and `tools_install_vscode`.

### 9. System Flatpaks & Flathub Remote (`tasks/flatpak.yml`)
- Configures the official Flathub remote repository (`https://dl.flathub.org/repo/flathub.flatpakrepo`) under system scope (`method: system`).
- Deploys administrative, utility, and creative Flatpak applications defined in `tools_system_flatpaks` (overridable via `system_flatpaks`).
- Gated by `tools_install_gui_apps` and `tools_install_flatpaks`.

### 10. Hardware Key Remapper (`tasks/input-remapper.yml`)
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
| `tools_install_transcribe` | `true` | Enable/disable transcribe.cpp compilation. |
| `tools_transcribe_require_min_specs` | `true` | Skip compilation if host has fewer than minimum cores or RAM. |
| `tools_transcribe_require_gpu` | `true` | Skip compilation if neither CUDA nor Vulkan devices are detected. |
| `tools_install_go` | `true` | Enable/disable Go toolchain environment validation. |
| `tools_go_min_version` | `"1.22"` | Minimum Go compiler version required in PATH. |
| `tools_install_antigravity` | `true` | Enable/disable Google Antigravity CLI (`agy`). |
| `tools_install_claude` | `true` | Enable/disable Claude Code CLI. |
| `tools_install_crush` | `true` | Enable/disable Charm Crush CLI. |
| `tools_install_opencode` | `true` | Enable/disable OpenCode CLI. |
| `tools_install_gui_apps` | `{{ auto_enable_desktop \| default(true) \| bool }}` | Master gate for graphical desktop applications. |
| `tools_install_vscode` | `{{ tools_install_gui_apps }}` | Enable/disable Visual Studio Code installation. |
| `tools_vscode_flatpak` | `false` | When true, installs VS Code via Flatpak instead of native RPM. |
| `tools_vscode_force_install` | `false` | When true, forces installation even if `code` binary is present. |
| `tools_install_antigravity_gui` | `{{ tools_install_gui_apps }}` | Enable/disable Antigravity Hub and IDE GUI binaries. |
| `tools_antigravity_state` | `"present"` | State of Antigravity Hub and IDE (`present` or `absent`). |
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
| `agents` | Subsystem | Targets all AI coding agent CLI tasks (`agy`, `claude`, `crush`, `opencode`). |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `bun` | Feature | Runs only Bun installation tasks. |
| `transcribe` | Feature | Runs only transcribe.cpp hardware detection and build tasks. |
| `go` | Feature | Runs only Go toolchain environment validation tasks. |
| `antigravity` | Feature | Runs only Antigravity CLI and Hub/IDE tasks. |
| `claude` | Feature | Runs only Claude Code CLI tasks. |
| `crush` | Feature | Runs only Crush CLI tasks. |
| `opencode` | Feature | Runs only OpenCode CLI tasks. |
| `vscode` | Feature | Runs only Visual Studio Code installation tasks. |
| `flathub` | Feature | Ensures system Flathub remote repository is configured. |
| `flatpaks` | Feature | Deploys system Flatpak applications. |
| `input-remapper` | Feature | Builds and configures input-remapper systemd daemon. |
| `always` | System | Preamble debug logging. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks (`playbooks/workstation.yml`)

```yaml
- name: Host Tools and Coding Agent Utilities
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
