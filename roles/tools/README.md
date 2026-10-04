# Tools Role (`roles/tools`)

Provisions host-level command-line tools, compiled hardware-accelerated utilities, user-space modern Go toolchains, and AI coding agent CLIs.

## Scope & Taxonomy

In accordance with the [distribution taxonomy](../../docs/layering-architecture.md):
- **Ansible (`roles/tools`)**:
  - Manages root-owned system-wide binaries in `/usr/local/bin` (`bun`, `transcribe.cpp`) and compiles host-specific hardware acceleration.
  - Manages user-scoped toolchain binaries and AI coding agent CLIs in `~/.local/bin` (`go`, `agy`, `claude`, `crush`, `opencode`, `vibe`) via `become_user: "{{ tools_user }}"`.
- **Yadm**: Manages user configuration files (`~/.gemini/antigravity-cli/settings.json`, `~/.claude/settings.json`, `~/.config/crush/crushrc`, `~/.config/opencode/opencode.json`, `~/.vibe/config.toml`), user toolchains (`rbenv`, `rustup`), and shared skills/agents directories (`~/.agents/skills`).

## Components

### 1. Bun (`tasks/bun.yml`)
Installs the official [Bun](https://bun.sh/) standalone JavaScript runtime to `/usr/local/bin/bun`.
- Architecture-aware download for `x86_64` and `aarch64`.
- Skips re-installation if `/usr/local/bin/bun` is already executable unless `tools_bun_force_install: true`.

### 2. Transcribe.cpp (`tasks/transcribe-cpp.yml`)
Clones and compiles [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) (Whisper-based audio transcription CLI) with automatic hardware acceleration detection:
- **GPU Accelerator Pre-flight Check**: Probes for hardware CUDA devices (`nvidia-smi`, `/dev/nvidia*`, sysfs PCI vendor `0x10de`) and Vulkan physical GPU devices (`vulkaninfo`, DRM render nodes). If neither CUDA nor Vulkan hardware devices are present, transcribe.cpp compilation is automatically **skipped** by default (`tools_transcribe_require_gpu: true`).
- **CUDA (NVIDIA)**: Detected CUDA device + `command -v nvcc` &rarr; builds with `GGML_CUDA=ON` and `TRANSCRIBE_CUDA=ON`.
- **Intel oneAPI / SYCL**: Probes `command -v icx` or `dpcpp` &rarr; builds with `GGML_SYCL=ON`.
- **Vulkan**: Detected Vulkan physical GPU (Intel Iris/Arc, AMD Radeon, NVIDIA) &rarr; builds with `GGML_VULKAN=ON` and `TRANSCRIBE_VULKAN=ON`.
- **CPU (Fallback)**: Defaults to CPU build only when GPU gating is disabled (`tools_transcribe_require_gpu: false`).
- Installs binary to `/usr/local/bin/transcribe`.
- Fully idempotent: checks existing binary state before initiating pre-flight checks and recompilation.

### 3. User-Space Go Toolchain (`tasks/go.yml`)
Installs the official standalone Go distribution into `~/.local/go` and symlinks binaries into `~/.local/bin/go`.
- Guarantees modern Go toolchain availability (e.g. Go 1.27+) for compiling Go-based CLIs on enterprise distributions like Enterprise Linux 10 where distro packages may lag behind.
- Idempotently probes `go version` and only downloads/re-extracts when missing, older than `tools_go_version`, or when forced.

### 4. Antigravity CLI (`tasks/antigravity.yml`)
Installs the official Google Antigravity CLI (`agy`) into `~/.local/bin/agy`.
- Idempotent stat check ensures installation script only runs when binary is missing or forced.
- All settings and MCP server configurations are managed by Yadm.

### 5. Claude Code CLI (`tasks/claude.yml`)
Installs Anthropic's Claude Code CLI (`@anthropic-ai/claude-code`) via user-prefixed `npm install -g`.
- Idempotent stat check verifies `~/.local/bin/claude`.
- All settings (`~/.claude/settings.json`) and MCP servers (`~/.claude/.mcp.json`) are managed by Yadm.

### 6. Crush CLI (`tasks/crush.yml`)
Compiles and installs Charm's Crush CLI (`github.com/charmbracelet/crush@latest`) using the user Go toolchain.
- Binaries land in `~/go/bin/crush` and are symlinked to `~/.local/bin/crush`.
- Idempotent stat check prevents redundant network queries and compilation.
- Configuration (`~/.config/crush/crushrc`) is managed by Yadm.

### 7. OpenCode CLI (`tasks/opencode.yml`)
Installs the OpenCode CLI (`opencode-ai`) via user-prefixed `npm install -g`.
- Idempotent stat check verifies `~/.local/bin/opencode`.
- Configuration (`~/.config/opencode/opencode.json`) is managed by Yadm.

### 8. Mistral Vibe CLI (`tasks/vibe.yml`)
Installs Mistral's Vibe CLI (`mistral-vibe`) via `uv tool install`.
- Idempotent stat check verifies `~/.local/bin/vibe`.
- Configuration (`~/.vibe/config.toml`) is managed by Yadm.

## Variables

| Variable | Default | Description |
|---|---|---|
| `tools_user` | `{{ workstation_user \| default(user.name \| default(ansible_user_id)) }}` | Target workstation user for user-scoped tools |
| `tools_user_home` | `{{ user.home \| default('/home/' ~ tools_user) }}` | Home directory of target workstation user |
| `tools_user_local_bin` | `{{ tools_user_home }}/.local/bin` | User-scoped executable binary destination |
| `tools_user_go_bin` | `{{ tools_user_home }}/go/bin` | User-scoped Go binary destination |
| `tools_install_bun` | `true` | Enable/disable Bun installation |
| `tools_bun_url` | *(auto-detected)* | Download URL for official Bun zip archive |
| `tools_bun_dest` | `/usr/local/bin/bun` | Target executable binary destination |
| `tools_bun_force_install` | `false` | Force re-download and re-extraction |
| `tools_install_transcribe` | `true` | Enable/disable transcribe.cpp compilation |
| `tools_transcribe_require_gpu` | `true` | Skip compilation if neither CUDA nor Vulkan devices are present |
| `tools_transcribe_repo` | `https://github.com/handy-computer/transcribe.cpp.git` | Git repository URL |
| `tools_transcribe_version` | `main` | Git ref / branch / tag to compile |
| `tools_transcribe_build_dir` | `/tmp/transcribe.cpp-build` | Temporary CMake build directory |
| `tools_transcribe_dest` | `/usr/local/bin/transcribe` | Target executable binary destination |
| `tools_transcribe_force_build` | `false` | Force CMake rebuild even if binary is present |
| `tools_transcribe_cleanup` | `true` | Clean up CMake build directory after compilation |
| `tools_install_go` | `true` | Enable/disable user Go toolchain installation |
| `tools_go_version` | `1.27.1` | Go release version to download |
| `tools_go_url` | *(derived from version)* | Download URL for official Go archive |
| `tools_go_dest_dir` | `{{ tools_user_home }}/.local/go` | Destination directory for Go toolchain |
| `tools_go_force_install` | `false` | Force re-download of Go archive |
| `tools_install_antigravity` | `true` | Enable/disable Antigravity CLI installation |
| `tools_antigravity_install_url` | `https://antigravity.google/cli/install.sh` | Installer script URL |
| `tools_antigravity_force_install` | `false` | Force re-running Antigravity installer |
| `tools_install_claude` | `true` | Enable/disable Claude Code installation |
| `tools_claude_npm_package` | `@anthropic-ai/claude-code` | Npm package name |
| `tools_claude_force_install` | `false` | Force re-installing Claude Code npm package |
| `tools_install_crush` | `true` | Enable/disable Crush CLI installation |
| `tools_crush_go_package` | `github.com/charmbracelet/crush@latest` | Go package URL |
| `tools_crush_force_install` | `false` | Force re-compilation of Crush CLI |
| `tools_install_opencode` | `true` | Enable/disable OpenCode installation |
| `tools_opencode_npm_package` | `opencode-ai` | Npm package name |
| `tools_opencode_force_install` | `false` | Force re-installing OpenCode npm package |
| `tools_install_vibe` | `true` | Enable/disable Mistral Vibe installation |
| `tools_vibe_package` | `mistral-vibe` | Package name for `uv tool` |
| `tools_vibe_force_install` | `false` | Force re-installing Vibe tool |

## Tags

| Tag | Purpose |
|---|---|
| `tools` | Runs all tasks in this role |
| `system` | Functional group tag shared across system provisioning roles |
| `bun` | Runs only Bun installation tasks |
| `transcribe` | Runs only transcribe.cpp build tasks |
| `go` | Runs only user-space Go toolchain installation |
| `agents` | Runs all AI coding agent CLI installation tasks |
| `antigravity` | Runs only Antigravity CLI tasks |
| `claude` | Runs only Claude Code CLI tasks |
| `crush` | Runs only Crush CLI tasks |
| `opencode` | Runs only OpenCode CLI tasks |
| `vibe` | Runs only Mistral Vibe CLI tasks |

## Example Usage

```yaml
- name: Install system tools and coding agent CLIs
  hosts: localhost
  become: true
  roles:
    - role: tools
      vars:
        tools_install_transcribe: true
        tools_install_bun: true
        tools_install_claude: true
        tools_install_crush: true
```
