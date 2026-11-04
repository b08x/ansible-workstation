# Workstation Layering Architecture & Taxonomy

## The Architecture

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

One edge this diagram cannot draw points upward: `01-ansible-pull.sh` — Layer 2 triggers Layer 1 convergence (`ansible-pull` against `local.yml`) before user configuration is applied. See [`bootstrap.md`](bootstrap.md) for the bridge.

## The Three Layers, From the Floor Up

**OSBuild (Layer 0) is the floor.** It bakes the immutable base image — the bootc/OSTree container appliance definition, core compiler toolchains, virtualization and container runtimes, system DNF repository configurations, and the core kernel — and is built, never mutated.

**Ansible (Layer 1) is the machine.** It owns host-level RPMs, hardware acceleration and GPU drivers (CUDA, Vulkan, Intel oneAPI), system Flatpaks, system CLI binaries (`/usr/local/bin/{bun, transcribe}`), and system services (`sshd`, `zram`, `libvirtd`) — idempotent by contract, so a re-run against a converged host reports zero changes.

**Yadm (Layer 2) is the user.** It owns `$HOME`: dotfiles and Jinja2 config templates, user Cargo crates, user Ruby gems via rbenv, user-space Flatpaks, and the coding agent configs (`~/.claude/settings.json`, `~/.crushrc`) — the one layer a re-image does not erase.

---

## Layer Ownership Principles

### 1. Single Ownership
Each package, toolchain, or configuration file must have exactly one authoritative manager. If Yadm manages a package list (e.g. `cargo-packages.txt`, `default-gems.txt`), Ansible must not attempt parallel installation loops; if Ansible installs a system package via DNF, OSBuild does not duplicate it unless required in the minimal bootc image. The canonical case of violating the rule is [`failure point 2`](failure-points.md#2-one-file-one-owner): `base` and `tuning` both templated `/etc/systemd/zram-generator.conf` — `memtotal/2` in one, `min(ram, 8192)` in the other — and every run flapped the file between them, defeating idempotency by ownership rather than by task logic.

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

---

## Packaging Delivery Matrix

The full lookup: this is where single ownership stops being a principle and becomes a lookup — every kind of thing has exactly one row, and the row is the owner.

| Delivery Mechanism | Target Layer | Manager / Tool | Examples | Justification / Boundary Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Base RPM Packages** | OSBuild | `osbuild` / `bootc` | `kernel`, `podman`, `gcc`, `glibc`, `cosmic-desktop` | Immutable appliance foundations. Baked at build time with DNF/DNF5 package management. |
| **Host RPM Packages** | Ansible | `ansible.builtin.dnf` (DNF / DNF5 validated) | `sox`, `tesseract-devel`, `yad`, `wl-clipboard`, `@gnome-desktop`, `@cosmic-desktop` | Dynamic host capabilities, desktop environments (GNOME & COSMIC), hardware dev libraries. Validated on DNF5 (Fedora 44) and DNF (AlmaLinux 10 / Rocky Linux 10). |
| **System Binaries** | Ansible | [`roles/tools`](../roles/tools) | `/usr/local/bin/bun`, `/usr/local/bin/transcribe` | Globally shared utilities requiring compilation or system-wide drop. `transcribe` is gated on CUDA/Vulkan GPU hardware presence. |
| **GPU Vendor Stacks** | Ansible | [`roles/gpu`](../roles/gpu) | `intel-oneapi-*` pinned MKL/compiler set, `nvidia-driver`, `cuda-toolkit`, `nvidia-container-toolkit` + CDI service | Optional per-host stacks gated by Tier 1 `intel_oneapi_install` / `nvidia_cuda_install`; tools and common probe only. |
| **System Flatpaks** | Ansible | [`roles/tools/tasks/flatpak.yml`](../roles/tools/tasks/flatpak.yml) | `ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy` | System-wide utility and administration GUI applications. |
| **User Flatpaks** | Yadm | `yadm/bootstrap.d/80-install-user-flatpaks.sh` | `Obsidian`, `Typora`, `Audacity`, `freac`, `Helvum`, `Podman Desktop`, `DBeaver` | User productivity, authoring, and media creation applications installed per-user. |
| **User Rust / Cargo** | Yadm | `yadm/bootstrap.d/20-cargo.sh` | `bottom`, `choose`, `git-cliff`, `gping`, `ripgrep_all`, `sd`, `gitui`, `eza` | Unprivileged user CLI tools compiled against user rustup toolchain in `~/.cargo/bin`. Removed from Ansible. |
| **User Ruby Gems** | Yadm | `yadm/bootstrap.d/30-ruby.sh` | `pry`, `solargraph`, `ruby-lsp`, `rubocop`, `bubblezone`, `huh`, `ntcharts` | User gemsets installed against rbenv Rubies in `~/.local/bin`. |
| **Python Environments** | Ansible + Yadm | Ansible (binary), Yadm (environment) | `uv`, `python3.14` (Fedora 44) / `python3.12+` (EL 10) (Ansible); `UV_PYTHON_PREFERENCE="only-managed"` (Yadm) | Ansible installs system Python and uv runtimes; user dotfiles set shell resolution policies. |
| **Coding Agents** | Ansible + Yadm | [`playbooks/agent-harness/`](../playbooks/agent-harness/) (binaries), Yadm (config) | CLI binaries (`agy`, `claude`, `crush`, `opencode`); configs via `~/.claude/`, `~/.config/crush/` | Ansible [`playbooks/agent-harness/`](../playbooks/agent-harness/) manages binaries; Yadm manages configs and shared skills. |
| **Bootstrap Orchestration** | Yadm &rarr; Ansible | `01-ansible-pull.sh` | `ansible-pull` targeting [`local.yml`](../local.yml) | Automated orchestration bridge between Layer 2 (Yadm) and Layer 1 (Ansible). Converges host state prior to applying user configurations. |
| **Homebrew (Linuxbrew)**| Opt-In Only | `tools_install_homebrew: false` | `/home/linuxbrew/.linuxbrew` | Disabled by default across all profiles to prevent unmanaged duplicate toolchains. |
