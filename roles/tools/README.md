# Ansible Role: tools

Provisions host-level command-line utilities, hardware-accelerated compiled binaries, Go toolchain environment validation (>= 1.22), and AI coding agent command-line interfaces (`agy`, `claude`, `crush`, `opencode`, `vibe`) across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `tools` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy root-owned system binaries (`/usr/local/bin`) and user-scoped executable tools (`~/.local/bin`).

It establishes a strict boundary separating binary installation from user configuration: Ansible installs executable toolchains and agent binaries, while **Layer 2 (Yadm)** manages user dotfiles, API keys, agent skills, and application configuration files.

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Configuration Files & Shared Agent Skills:                             |
|   ~/.gemini/antigravity-cli/settings.json, ~/.claude/settings.json,      |
|   ~/.config/crush/crushrc, ~/.config/opencode/, ~/.vibe/config.toml,     |
|   ~/.agents/skills/                                                      |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/tools (Ansible)                      |
|   - System Binaries (/usr/local/bin):                                    |
|       * Bun Standalone JS/TS Runtime (bun)                               |
|       * Hardware-Accelerated Audio Transcription (transcribe.cpp)        |
|   - User Toolchains & Coding Agent CLIs (~/.local/bin & ~/go/bin):       |
|       * Go Compiler Validation (>= 1.22 in PATH)                         |
|       * Google Antigravity CLI (agy)                                     |
|       * Anthropic Claude Code CLI (claude)                               |
|       * Charm Crush CLI (Go-compiled in ~/go/bin and ~/.local/bin)       |
|       * OpenCode CLI (opencode)                                          |
|       * Mistral Vibe CLI (vibe via uv tool)                              |
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

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular tool installers (`bun.yml`, `transcribe-cpp.yml`, `go.yml`, `antigravity.yml`, `claude.yml`, `crush.yml`, `opencode.yml`, `vibe.yml`) gated by explicit boolean feature flags (`tools_install_*`). Specifically, `go.yml` performs fail-fast Go environment validation.
2. **Pre-flight Hardware Capability Checks**:
   - `tasks/transcribe-cpp.yml` probes the host for CUDA hardware devices (`nvidia-smi`, `/dev/nvidia*`, PCI vendor `0x10de`) and Vulkan physical GPU devices (`vulkaninfo`, render nodes).
   - If neither CUDA nor Vulkan hardware devices are present and `tools_transcribe_require_gpu: true`, compilation is automatically **skipped** with an informative debug notice rather than failing or wasting resources on CPU builds.
3. **Failure-Shape Pattern (Shape 2: True Fallback & Auto-Detection)**:
   - Evaluates hardware acceleration tiers for Whisper transcription: CUDA (`GGML_CUDA=ON`) &rarr; Intel SYCL/oneAPI (`GGML_SYCL=ON`) &rarr; Vulkan (`GGML_VULKAN=ON`) &rarr; CPU fallback.
4. **Idempotency Stat Guards & Check-Mode Safety**: Every installer performs a preliminary stat check or version probe (`bun`, `transcribe`, `agy`, `claude`, `crush`, `opencode`, `vibe`) to bypass redundant archive downloads, git checkouts, and compilations on converged hosts. Probe commands (`which npm`, `which uv`, `which go`, `go version`) declare `check_mode: false` and defensive filters (`rc | default(1)`).
5. **User Context & Runtime Isolation (`become_user`)**: User-scoped tools and Go-compiled utilities install strictly under `become_user: "{{ tools_user }}"`, preserving unprivileged home directory ownership. Additionally, npm global installs (`claude`, `opencode`) define `TMPDIR: "/run/user/{{ user.uid }}/tmp"` under unprivileged `become_user` to eliminate tempfile permission collisions.
6. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`tools`, `agents`, `system`) and dedicated tool tags (`bun`, `transcribe`, `go`, `antigravity`, `claude`, `crush`, `opencode`, `vibe`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `user.home`) and Tier 2 namespaced role variables (`tools_*`).
8. **Pre-flight Assertion Pattern**: Frontloads prerequisite validation (`tasks/assert.yml`) to fail fast when prerequisites (OS family, effective root privileges, target user configuration, Go toolchain parameters) are missing or misconfigured.

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
  - **Intel oneAPI / SYCL**: Probes `icx` or `dpcpp` &rarr; compiles with `-DGGML_SYCL=ON`.
  - **Vulkan**: Probes Vulkan physical GPUs (Intel Iris/Arc, AMD Radeon, NVIDIA) &rarr; compiles with `-DGGML_VULKAN=ON -DTRANSCRIBE_VULKAN=ON`.
  - **GPU Requirement Gate**: Controlled by `tools_transcribe_require_gpu: true` (default). When no GPU accelerator is found, cleanly skips compilation.
- Installs binary to `/usr/local/bin/transcribe`.

### 3. Go Toolchain Environment Validation (`tasks/go.yml`)
- Verifies that a valid Go compiler (>= 1.22, controlled by `tools_go_min_version`) is available in `PATH`.
- Prepares user binary and Go workspace directories (`~/.local/bin` and `~/go/bin`) under target user ownership.
- Probes compiler availability and version using `which go` and `go version` with check-mode safe flags.
- Asserts environment readiness via `ansible.builtin.assert`, failing fast with guidance to install Go via package manager (e.g. `dnf install golang`) if Go is absent or below the required version.

### 4. Google Antigravity CLI (`tasks/antigravity.yml`)
- Installs the official Google Antigravity CLI (`agy`) into `~/.local/bin/agy`.
- Stat guard ensures installation script only executes when the binary is absent or forced.

### 5. Anthropic Claude Code CLI (`tasks/claude.yml`)
- Installs Anthropic's Claude Code CLI (`@anthropic-ai/claude-code`) via user npm global prefix into `~/.local/bin/claude`.
- Stat check verifies `~/.local/bin/claude`.
- Applies `TMPDIR: "/run/user/{{ user.uid }}/tmp"` runtime isolation under unprivileged `become_user` to eliminate tempfile permission collisions during npm global installation.

### 6. Charm Crush CLI (`tasks/crush.yml`)
- Compiles Charm's Crush CLI (`github.com/charmbracelet/crush@latest`) using Go (`go install`).
- Installs binary to `~/go/bin/crush` and symlinks into `~/.local/bin/crush`.
- Sets `GOTOOLCHAIN: "auto"` parameter in the build environment to ensure smooth compilation when dependencies require newer toolchains than host default (overriding Fedora's system-wide `GOTOOLCHAIN=local` setting).

### 7. OpenCode CLI (`tasks/opencode.yml`)
- Installs OpenCode (`opencode-ai`) via user npm global prefix into `~/.local/bin/opencode`.
- Stat check verifies `~/.local/bin/opencode`.
- Implements `TMPDIR: "/run/user/{{ user.uid }}/tmp"` runtime isolation under unprivileged `become_user` to eliminate tempfile permission collisions.

### 8. Mistral Vibe CLI (`tasks/vibe.yml`)
- Installs Mistral's Vibe CLI (`mistral-vibe`) via `uv tool install` into `~/.local/bin/vibe`.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Bun Runtime** | `/usr/local/bin/bun` | `/usr/local/bin/bun` | `/usr/local/bin/bun` |
| **Transcribe.cpp** | CUDA / Vulkan / CPU | CUDA / Vulkan / CPU | CUDA / Vulkan / CPU |
| **Go Toolchain** | System Go (>= 1.22 in PATH) | System Go (>= 1.22 in PATH) | System Go (>= 1.22 in PATH) |
| **Antigravity CLI** | `~/.local/bin/agy` | `~/.local/bin/agy` | `~/.local/bin/agy` |
| **Claude Code CLI** | `~/.local/bin/claude` | `~/.local/bin/claude` | `~/.local/bin/claude` |
| **Crush CLI** | `~/.local/bin/crush` | `~/.local/bin/crush` | `~/.local/bin/crush` |
| **OpenCode CLI** | `~/.local/bin/opencode`| `~/.local/bin/opencode`| `~/.local/bin/opencode`|
| **Mistral Vibe CLI** | `~/.local/bin/vibe` | `~/.local/bin/vibe` | `~/.local/bin/vibe` |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT). |
| `user.home` | `"/home/" ~ user.name` | Home directory of primary workstation user. |
| `has_cuda_device` | *(undefined)* | Optional pre-flight override for CUDA device detection. |
| `has_vulkan_device` | *(undefined)* | Optional pre-flight override for Vulkan device detection. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `tools_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `tools_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`) to fail fast on invalid environments. |
| `tools_user` | `{{ user.name }}` | Target workstation user for user-scoped tools. |
| `tools_user_home` | `{{ user.home }}` | Home directory of target user. |
| `tools_user_local_bin` | `{{ tools_user_home }}/.local/bin` | User binary execution directory. |
| `tools_user_go_bin` | `{{ tools_user_home }}/go/bin` | User Go binary execution directory. |
| `tools_install_bun` | `true` | Enable/disable Bun installation. |
| `tools_bun_dest` | `"/usr/local/bin/bun"` | Destination path for Bun executable. |
| `tools_bun_force_install` | `false` | Force re-download and re-extraction of Bun. |
| `tools_install_transcribe` | `true` | Enable/disable transcribe.cpp compilation. |
| `tools_transcribe_require_min_specs` | `true` | Skip compilation if host has fewer than minimum cores or RAM. |
| `tools_transcribe_min_cores` | `16` | Minimum CPU cores/vCPUs required to build transcribe.cpp. |
| `tools_transcribe_min_mem_gb` | `32` | Minimum system RAM in GB required to build transcribe.cpp. |
| `tools_transcribe_require_gpu`| `true` | Skip compilation if neither CUDA nor Vulkan devices are detected. |
| `tools_transcribe_dest` | `"/usr/local/bin/transcribe"` | Destination path for transcribe binary. |
| `tools_transcribe_force_build`| `false` | Force CMake rebuild even if binary exists. |
| `tools_install_go` | `true` | Enable/disable Go toolchain environment validation. |
| `tools_go_min_version` | `"1.22"` | Minimum Go compiler version required in PATH. |
| `tools_install_antigravity` | `true` | Enable/disable Google Antigravity CLI. |
| `tools_install_claude` | `true` | Enable/disable Claude Code CLI. |
| `tools_install_crush` | `true` | Enable/disable Charm Crush CLI. |
| `tools_install_opencode` | `true` | Enable/disable OpenCode CLI. |
| `tools_install_vibe` | `true` | Enable/disable Mistral Vibe CLI. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `tools` | Role | Applies to all tasks within the `tools` role. |
| `assert` | Validation | Executes pre-flight assertion tasks to validate system requirements and privileges. |
| `agents` | Subsystem | Targets all AI coding agent CLI installation tasks (`agy`, `claude`, `crush`, `opencode`, `vibe`). |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `bun` | Feature | Runs only Bun installation tasks. |
| `transcribe` | Feature | Runs only transcribe.cpp hardware detection and build tasks. |
| `go` | Feature | Runs only Go toolchain environment validation tasks. |
| `antigravity` | Feature | Runs only Antigravity CLI tasks. |
| `claude` | Feature | Runs only Claude Code CLI tasks. |
| `crush` | Feature | Runs only Crush CLI tasks. |
| `opencode` | Feature | Runs only OpenCode CLI tasks. |
| `vibe` | Feature | Runs only Mistral Vibe CLI tasks. |
| `always` | System | Preamble debug logging. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included in `playbooks/workstation.yml`:

```yaml
- name: Developer Tools & Coding Agents
  hosts: workstations
  become: true
  roles:
    - role: tools
      tags: ["tools", "agents"]
```

### 2. Autonomous Local Provisioning (`local.yml`)

In `local.yml`, executed during local workstation bootstrap:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: tools
      tags: ["tools", "agents"]
```

### 3. Execution Commands

Run only coding agent CLI installations:

```bash
ansible-playbook playbooks/workstation.yml --tags "agents"
```

Rebuild transcribe.cpp with force build flag:

```bash
ansible-playbook local.yml --tags "transcribe" -e "tools_transcribe_force_build=true"
```

Validate Go toolchain environment:

```bash
ansible-playbook local.yml --tags "go"
```

---

## Verification & Health Checks

After role convergence, verify tool availability:

### 1. System Binaries Verification

```bash
# Verify Bun runtime
bun --version

# Verify Transcribe.cpp binary and help menu
transcribe --help
```

### 2. User Toolchain & Go Verification

```bash
# Verify Go compiler
go version

# Verify Go-compiled Crush CLI
~/.local/bin/crush --version
```

### 3. Coding Agent CLIs Verification

```bash
# Verify Antigravity CLI
~/.local/bin/agy --version

# Verify Claude Code CLI
~/.local/bin/claude --version

# Verify Crush CLI
~/.local/bin/crush --version

# Verify OpenCode CLI
~/.local/bin/opencode --version

# Verify Mistral Vibe CLI
~/.local/bin/vibe --version
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/tools
```

Execute role unit testing via the provided test play:

```bash
ansible-playbook roles/tools/tests/test.yml -i roles/tools/tests/inventory --check
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
