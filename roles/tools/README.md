# Tools Role (`roles/tools`)

Provisions host-level command-line tools and utilities that require system-wide binary placement or compiled hardware acceleration.

## Scope & Taxonomy

In accordance with the [distribution taxonomy](../../docs/layering-architecture.md):
- **Ansible (`roles/tools`)**: Manages root-owned system-wide binaries in `/usr/local/bin` (`bun`, `transcribe.cpp`) and compiles host-specific hardware acceleration.
- **Yadm**: Manages user-scoped toolchains (`rbenv`, `rustup`), default gems, and cargo crates in `$HOME/.cargo/bin`.

## Components

### 1. Bun (`tasks/bun.yml`)
Installs the official [Bun](https://bun.sh/) standalone JavaScript runtime to `/usr/local/bin/bun`.
- Architecture-aware download for `x86_64` and `aarch64`.
- Skips re-installation if `/usr/local/bin/bun` is already executable unless `tools_bun_force_install: true`.

### 2. Transcribe.cpp (`tasks/transcribe-cpp.yml`)
Clones and compiles [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) (Whisper-based audio transcription CLI) with automatic hardware acceleration detection:
- **CUDA (NVIDIA)**: Probes `command -v nvcc` &rarr; builds with `GGML_CUDA=ON`.
- **Intel oneAPI / SYCL**: Probes `command -v icx` or `dpcpp` &rarr; builds with `GGML_SYCL=ON`.
- **CPU (Fallback)**: Defaults to CPU build with AVX2 vector optimizations.
- Installs binary to `/usr/local/bin/transcribe`.
- Fully idempotent: checks existing binary state and git commit SHA before recompiling.

## Variables

| Variable | Default | Description |
|---|---|---|
| `tools_install_bun` | `true` | Enable/disable Bun installation |
| `tools_bun_url` | *(auto-detected)* | Download URL for the official Bun zip archive |
| `tools_bun_dest` | `/usr/local/bin/bun` | Target executable binary destination |
| `tools_bun_force_install` | `false` | Force re-download and re-extraction |
| `tools_install_transcribe` | `true` | Enable/disable transcribe.cpp compilation |
| `tools_transcribe_repo` | `https://github.com/handy-computer/transcribe.cpp.git` | Git repository URL |
| `tools_transcribe_version` | `main` | Git ref / branch / tag to compile |
| `tools_transcribe_build_dir` | `/tmp/transcribe.cpp-build` | Temporary CMake build directory |
| `tools_transcribe_dest` | `/usr/local/bin/transcribe` | Target executable binary destination |
| `tools_transcribe_force_build` | `false` | Force CMake rebuild even if binary is present |

## Tags

| Tag | Purpose |
|---|---|
| `tools` | Runs all tasks in this role |
| `bun` | Runs only Bun installation tasks |
| `transcribe` | Runs only transcribe.cpp build tasks |
| `system` | Functional group tag shared across system provisioning roles |

## Example Usage

```yaml
- name: Install system tools
  hosts: localhost
  become: true
  roles:
    - role: tools
      vars:
        tools_install_transcribe: true
        tools_install_bun: true
```
