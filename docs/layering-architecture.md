# Workstation Layering Architecture & Taxonomy

## Architecture Overview

The Syncopated workstation platform uses a three-tier layered architecture establishing strict boundaries of ownership between immutable base operating systems, mutable host orchestration, and unprivileged user space.

```
+--------------------------------------------------------------------------+
|                                  Yadm                                    |
|  Unprivileged User Space ($HOME, Dotfiles, User Toolchains, User Apps)   |
|  - Dotfiles (~/.zshrc, ~/.bashrc, config templates via Jinja2)           |
|  - User Cargo crates (~/.config/yadm/cargo-packages.txt)                 |
|  - User Ruby gems (~/.config/yadm/default-gems.txt via rbenv)            |
|  - User-space Flatpaks (bootstrap.d/80-install-user-flatpaks.sh)         |
|  - Coding agent configs (~/.claude/settings.json, ~/.crushrc)            |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                                 Ansible                                  |
|   Machine & Host Orchestration (System Configuration & System Services)  |
|  - Host-level RPMs (sox, tesseract-devel, yad, wl-clipboard)             |
|  - Hardware acceleration & GPU drivers (CUDA, Vulkan, Intel oneAPI)      |
|  - System Flatpaks (ExtensionManager, Flatseal, Warehouse, BoxBuddy)     |
|  - System CLI binaries (/usr/local/bin/{bun, transcribe})                 |
|  - System services (sshd, zram, libvirtd)                                |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                                 OSBuild                                  |
|              Immutable Base Image / Appliance Layer                      |
|  - Bootc / OSTree container appliance definition                         |
|  - Core compiler toolchains (gcc, gcc-c++, make, cmake)                  |
|  - Virtualization & container runtimes (podman, buildah, qemu, libvirt)  |
|  - System DNF repository configurations and core kernel                  |
+--------------------------------------------------------------------------+
```

---

## Packaging Delivery Matrix

| Delivery Mechanism | Target Layer | Manager / Tool | Examples | Justification / Boundary Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Base RPM Packages** | OSBuild | `osbuild` / `bootc` | `kernel`, `podman`, `gcc`, `glibc` | Immutable appliance foundations. Baked at build time with DNF/DNF5 package management. |
| **Host RPM Packages** | Ansible | `ansible.builtin.dnf` (DNF / DNF5 validated) | `sox`, `tesseract-devel`, `yad`, `wl-clipboard`, `fzf` | Dynamic host capabilities, desktop environments, hardware dev libraries. Validated on DNF5 (Fedora 44) and DNF (AlmaLinux 10 / Rocky Linux 10). |
| **System Binaries** | Ansible | [`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools) | `/usr/local/bin/bun`, `/usr/local/bin/transcribe` | Globally shared utilities requiring compilation or system-wide drop. `transcribe` is gated on CUDA/Vulkan GPU hardware presence. |
| **System Flatpaks** | Ansible | [`roles/desktop/tasks/flatpak.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/desktop/tasks/flatpak.yml) | `ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy` | System-wide utility and administration GUI applications. |
| **User Flatpaks** | Yadm | `yadm/bootstrap.d/80-install-user-flatpaks.sh` | `Obsidian`, `Typora`, `Audacity`, `freac`, `Helvum`, `Podman Desktop`, `DBeaver` | User productivity, authoring, and media creation applications installed per-user. |
| **User Rust / Cargo** | Yadm | `yadm/bootstrap.d/20-cargo.sh` | `bottom`, `choose`, `git-cliff`, `gping`, `ripgrep_all`, `sd`, `gitui`, `eza` | Unprivileged user CLI tools compiled against user rustup toolchain in `~/.cargo/bin`. Removed from Ansible. |
| **User Ruby Gems** | Yadm | `yadm/bootstrap.d/30-ruby.sh` | `pry`, `solargraph`, `ruby-lsp`, `rubocop`, `bubblezone`, `huh`, `ntcharts` | User gemsets installed against rbenv Rubies in `~/.local/bin`. |
| **Python Environments** | Ansible + Yadm | Ansible (binary), Yadm (environment) | `uv`, `python3.14` (Fedora 44) / `python3.12+` (EL 10) (Ansible); `UV_PYTHON_PREFERENCE="only-managed"` (Yadm) | Ansible installs system Python and uv runtimes; user dotfiles set shell resolution policies. |
| **Coding Agents** | Ansible + Yadm | [`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools) (binaries), Yadm (config) | CLI binaries (`agy`, `claude`, `crush`, `opencode`, `vibe`); configs via `~/.claude/`, `~/.config/crush/` | Ansible [`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools) manages binaries; Yadm manages configs and shared skills. |
| **Bootstrap Orchestration** | Yadm &rarr; Ansible | `01-ansible-pull.sh` | `ansible-pull` targeting [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) | Automated orchestration bridge between Layer 2 (Yadm) and Layer 1 (Ansible). Converges host state prior to applying user configurations. |
| **Homebrew (Linuxbrew)**| Opt-In Only | `base_install_homebrew: false` | `/home/linuxbrew/.linuxbrew` | Disabled by default across all profiles to prevent unmanaged duplicate toolchains. |

---

## Layer Ownership Principles

### 1. Single Ownership
Each package, toolchain, or configuration file must have exactly one authoritative manager.
- If Yadm manages a package list (e.g. `cargo-packages.txt`, `default-gems.txt`), Ansible must not attempt parallel installation loops.
- If Ansible installs a system package via DNF, OSBuild does not duplicate it unless required in the minimal bootc image.

### 2. No Template Clobbering
Ansible roles must never overwrite dotfiles or configurations tracked by Yadm in `$HOME`. When Ansible drops helper configurations, it must check for existing user files or gate deployments to prevent clobbering user customizations.

### 3. Separation of Binaries and Dotfiles
System and toolchain binaries belong in `/usr/local/bin` (provisioned by Ansible) or `$HOME/.local/bin` / `$HOME/.cargo/bin` (provisioned by unprivileged user toolchains via Yadm). Shell environments, aliases, and shell initialization belong strictly to Yadm dotfiles (`.zshrc##template.j2`).

### 4. Fail-Fast Preconditions and Check-Mode Safety
Every Ansible role frontloads assertions in `tasks/assert.yml` to fail fast (< 1s) when runtime invariants are violated:
- **Distribution & Package Manager**: Validates `ansible_os_family == 'RedHat'` and package manager in `['dnf', 'dnf5']`, ensuring verified parity across Fedora 44, AlmaLinux 10, and Rocky Linux 10.
- **Elevation**: Confirms effective root permissions (`id -u == 0`) before attempting mutations.
- **Identity Fact Propagation**: Verifies `user.name` is resolved to prevent orphan files or mismatched home directories.
- **Check-Mode Safety**: All assertions, capability probes, and stat tasks enforce `check_mode: false` so that dry-run validations (`--check`) report accurate diagnostics without halting prematurely. A converged host re-run with `--check` reports zero changes.
