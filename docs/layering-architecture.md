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
| **Base RPM Packages** | OSBuild | `osbuild` / `bootc` | `kernel`, `podman`, `gcc`, `glibc` | Immutable appliance foundations. Baked at build time. |
| **Host RPM Packages** | Ansible | `ansible.builtin.dnf` | `sox`, `tesseract-devel`, `yad`, `wl-clipboard`, `fzf` | Dynamic host capabilities, desktop environments, hardware dev libraries. |
| **System Binaries** | Ansible | `roles/tools` | `/usr/local/bin/bun`, `/usr/local/bin/transcribe` | Globally shared utilities requiring compilation or system-wide drop. `transcribe` is gated on CUDA/Vulkan GPU hardware presence. |
| **System Flatpaks** | Ansible | `roles/desktop/tasks/flatpak.yml` | `ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy` | System-wide utility and administration GUI applications. |
| **User Flatpaks** | Yadm | `yadm/bootstrap.d/80-install-user-flatpaks.sh` | `Obsidian`, `Typora`, `Audacity`, `freac`, `Helvum`, `Podman Desktop`, `DBeaver` | User productivity, authoring, and media creation applications installed per-user. |
| **User Rust / Cargo** | Yadm | `yadm/bootstrap.d/20-cargo.sh` | `bottom`, `choose`, `git-cliff`, `gping`, `ripgrep_all`, `sd`, `gitui`, `eza` | Unprivileged user CLI tools compiled against user rustup toolchain in `~/.cargo/bin`. Removed from Ansible. |
| **User Ruby Gems** | Yadm | `yadm/bootstrap.d/30-ruby.sh` | `pry`, `solargraph`, `ruby-lsp`, `rubocop`, `bubblezone`, `huh`, `ntcharts` | User gemsets installed against rbenv Rubies in `~/.local/bin`. |
| **Python Environments** | Ansible + Yadm | Ansible (binary), Yadm (environment) | `uv`, `python3.13` (Ansible); `UV_PYTHON_PREFERENCE="only-managed"` (Yadm) | Ansible installs python/uv runtimes; user dotfiles set shell resolution policies. |
| **Coding Agents** | Ansible + Yadm | `roles/tools` (binaries), Yadm (config) | CLI binaries (`agy`, `claude`, `crush`, `opencode`, `vibe`); configs via `~/.claude/`, `~/.config/crush/` | Ansible `roles/tools` manages binaries; Yadm manages configs and shared skills. |

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
