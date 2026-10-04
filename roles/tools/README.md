# Ansible Role: tools

Provisions host-level command-line utilities, hardware-accelerated compiled binaries, user-space modern Go toolchains, and AI coding agent command-line interfaces (`agy`, `claude`, `crush`, `opencode`, `vibe`) across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

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
|   - User Toolchains & Coding Agent CLIs (~/.local/bin):                  |
|       * Standalone Go Toolchain (go, gofmt) in ~/.local/go               |
|       * Google Antigravity CLI (agy)                                     |
|       * Anthropic Claude Code CLI (claude)                               |
|       * Charm Crush CLI (crush compiled via Go)                          |
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

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular tool installers (`bun.yml`, `transcribe-cpp.yml`, `go.yml`, `antigravity.yml`, `claude.yml`, `crush.yml`, `opencode.yml`, `vibe.yml`) gated by explicit boolean feature flags (`tools_install_*`).
2. **Pre-flight Hardware Capability Checks**:
   - `tasks/transcribe-cpp.yml` probes the host for CUDA hardware devices (`nvidia-smi`, `/dev/nvidia*`, PCI vendor `0x10de`) and Vulkan physical GPU devices (`vulkaninfo`, render nodes).
   - If neither CUDA nor Vulkan hardware devices are present and `tools_transcribe_require_gpu: true`, compilation is automatically **skipped** with an informative debug notice rather than failing or wasting resources on CPU builds.
3. **Failure-Shape Pattern (Shape 2: True Fallback & Auto-Detection)**:
   - Evaluates hardware acceleration tiers for Whisper transcription: CUDA (`GGML_CUDA=ON`) &rarr; Intel SYCL/oneAPI (`GGML_SYCL=ON`) &rarr; Vulkan (`GGML_VULKAN=ON`) &rarr; CPU fallback.
4. **Idempotency Stat Guards**: Every installer performs a preliminary stat check or version probe (`bun`, `transcribe`, `go version`, `agy`, `claude`, `crush`, `opencode`, `vibe`) to bypass redundant archive downloads, git checkouts, and compilations on converged hosts.
5. **User Context Isolation (`become_user`)**: User-scoped tools and Go toolchains compile and install strictly under `become_user: "{{ tools_user }}"`, preserving unprivileged home directory ownership.
6. **Tag-as-Select Pattern**: Every task is tagged with domain tags (`tools`, `agents`, `system`) and dedicated tool tags (`bun`, `transcribe`, `go`, `antigravity`, `claude`, `crush`, `opencode`, `vibe`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`, `user.home`) and Tier 2 namespaced role variables (`tools_*`).

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

### 3. User-Space Go Toolchain (`tasks/go.yml`)
- Provisions a standalone Go distribution directly into `~/.local/go` and symlinks `go` and `gofmt` to `~/.local/bin/go`.
- Solves enterprise distribution package lag (e.g. AlmaLinux / Rocky Linux 10 shipping older Go compilers) by providing modern Go (1.27+) for building developer CLIs.
- Probes `go version` and only downloads/re-extracts when missing or when older than `tools_go_version`.

### 4. Google Antigravity CLI (`tasks/antigravity.yml`)
- Installs the official Google Antigravity CLI (`agy`) into `~/.local/bin/agy`.
- Stat guard ensures installation script only executes when the binary is absent or forced.

### 5. Anthropic Claude Code CLI (`tasks/claude.yml`)
- Installs Anthropic's Claude Code CLI (`@anthropic-ai/claude-code`) via user npm global prefix.
- Stat check verifies `~/.local/bin/claude`.

### 6. Charm Crush CLI (`tasks/crush.yml`)
- Compiles Charm's Crush CLI (`github.com/charmbracelet/crush@latest`) using the user Go toolchain.
- Installs binary to `~/go/bin/crush` and symlinks into `~/.local/bin/crush`.

### 7. OpenCode CLI (`tasks/opencode.yml`)
- Installs OpenCode (`opencode-ai`) via user npm global prefix into `~/.local/bin/opencode`.

### 8. Mistral Vibe CLI (`tasks/vibe.yml`)
- Installs Mistral's Vibe CLI (`mistral-vibe`) via `uv tool install` into `~/.local/bin/vibe`.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Bun Runtime** | `/usr/local/bin/bun` | `/usr/local/bin/bun` | `/usr/local/bin/bun` |
| **Transcribe.cpp** | CUDA / Vulkan / CPU | CUDA / Vulkan / CPU | CUDA / Vulkan / CPU |
| **User Go Toolchain** | `~/.local/go` | `~/.local/go` | `~/.local/go` |
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
| `tools_user` | `{{ user.name }}` | Target workstation user for user-scoped tools. |
| `tools_user_home` | `{{ user.home }}` | Home directory of target user. |
| `tools_user_local_bin` | `{{ tools_user_home }}/.local/bin` | User binary execution directory. |
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
| `tools_install_go` | `true` | Enable/disable user Go toolchain installation. |
| `tools_go_version` | `"1.27.1"` | Go release version to download. |
| `tools_go_dest_dir` | `{{ tools_user_home }}/.local/go` | Installation path for Go toolchain. |
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
| `agents` | Subsystem | Targets all AI coding agent CLI installation tasks (`agy`, `claude`, `crush`, `opencode`, `vibe`). |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `bun` | Feature | Runs only Bun installation tasks. |
| `transcribe` | Feature | Runs only transcribe.cpp hardware detection and build tasks. |
| `go` | Feature | Runs only user-space Go toolchain installation. |
| `antigravity` | Feature | Runs only Antigravity CLI tasks. |
| `claude` | Feature | Runs only Claude Code CLI tasks. |
| `crush` | Feature | Runs only Crush CLI tasks. |
| `opencode` | Feature | Runs only OpenCode CLI tasks. |
| `vibe` | Feature | Runs only Mistral Vibe CLI tasks. |
| `always` | System | Preamble debug logging. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included in `playbooks/tools.yml` (and imported in `playbooks/site.yml`):

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
ansible-playbook playbooks/site.yml --tags "agents"
```

Rebuild transcribe.cpp with force build flag:

```bash
ansible-playbook local.yml --tags "transcribe" -e "tools_transcribe_force_build=true"
```

Update only the user Go toolchain:

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
# Verify user Go binary
~/.local/bin/go version
~/.local/bin/gofmt --help
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
