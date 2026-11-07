# Workstation Layering Architecture & Taxonomy

## The Architecture

The Syncopated workstation platform uses a decoupled, layered architecture establishing strict boundaries
of ownership between declarative intent specification, immutable base operating systems, deterministic
host orchestration, and unprivileged user space.

```
+--------------------------------------------------------------------------+
|                 NLUI & Gherkin Verification Gate Layer                   |
|  Natural Language User Interface -> Gherkin Requirement Specification    |
|  - High-level intent parsed into Feature / Scenario / Given / When / Then|
|  - Precondition validation & AST compilation to Ansible tasks & vars     |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                                  Yadm                                    |
|  Unprivileged User Space ($HOME, Dotfiles, User Toolchains, User Apps)   |
|  - Dotfiles (~/.zshrc, ~/.bashrc, config templates via Jinja2)           |
|  - User Cargo crates (~/.config/yadm/cargo-packages.txt)                 |
|  - User Ruby gems (~/.config/yadm/default-gems.txt via rbenv)            |
|  - User-space Flatpaks (bootstrap.d/80-install-user-flatpaks.sh)         |
|  - Coding agent configs (~/.claude/settings.json, ~/.config/crush/)      |
+--------------------------------------------------------------------------+
                                    |  ▲ (bootstrap.d/02-ansible-pull.sh
                                    |  │  bridges up to local.yml)
                                    v  │
+--------------------------------------------------------------------------+
|                                 Ansible                                  |
|   Deterministic Gate Validator & Host Orchestration (System Services)    |
|  - AST validation, argument spec verification, fail-fast gates (<1s)     |
|  - Host-level RPMs (sox, tesseract-devel, yad, wl-clipboard) via DNF5    |
|  - Hardware acceleration & GPU drivers (CUDA, Vulkan, Intel oneAPI)      |
|  - System Flatpaks (ExtensionManager, Flatseal, Warehouse, BoxBuddy)     |
|  - System CLI binaries (/usr/local/bin/transcribe, /usr/local/bin/inxi)  |
|  - User toolchains (~/.bun/bin, ~/.local/go, ~/.cargo) via roles/user    |
|  - System services (sshd, zram, libvirtd) with seat-aware handlers       |
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
                                    |
                                    v
+--------------------------------------------------------------------------+
|                        Fast Layer (Containers)                           |
|       Ephemeral & Sandboxed Execution (Podman, containerd)               |
+--------------------------------------------------------------------------+
```

An upward bridge connects Layer 2 back into Layer 1: `bootstrap.d/02-ansible-pull.sh` executes a privileged
`ansible-pull` targeting `local.yml`. This execution is conditional on the machine pull marker
`~/.initial-firstboot` located in the primary workstation user's home directory. If the marker is present,
the pull skips cleanly (`RC_SKIPPED`), ensuring that already-converged machines do not repeat system provisioning.
See [`bootstrap.md`](bootstrap.md) for the end-to-end bare-metal lifecycle.

---

## Ansible as Deterministic Gate Validator & Implementer

Within this layering model, Ansible functions not as a generic script runner, but as a
**deterministic execution engine and validation gate**:

1. **The Abstract Syntax Tree (AST) Contract**: In contrast to probabilistic LLM code generation,
   Ansible tasks are structured YAML documents backed by formal argument specifications (`argument_spec`).
   Every parameter, condition, loop, elevation flag, and module target is validated against Ansible's
   underlying AST parser before execution.
2. **Sub-Second Pre-Flight Assertion Gates (<1s)**: Every modular role in `roles/` frontloads
   `tasks/assert.yml` tagged `[<role>, assert, always]`. These assertions run in under one second to verify:
   - Distribution family (`ansible_os_family == 'RedHat'`).
   - Package manager presence (`dnf` or `dnf5`).
   - Init system status (`systemd`).
   - Elevation status (verifying effective root `id -u == 0` for system tasks).
   - Identity variables (`user.name`, `user.home`).
   If an agent or pipeline proposes a change that violates host invariants, the assertion gate halts
   execution instantly before mutating host state.
3. **Idempotency Guarantee**: Successive runs against a converged machine report `changed=0`. Any task
   that causes unwanted drift or flaps configuration is flagged as a defect.
4. **Controlled Memory and Kernel Staging**: As established in empirical Failure Point 1, kernel memory
   parameters (such as ZRAM swap algorithms) cannot be hot-reloaded under active memory load. Ansible
   stages configuration to disk and defers reload to reboot, eliminating runtime crashes.

---

## Natural Language User Interface (NLUI) & Gherkin-Gated Pipeline

Above Layer 2 sits the Natural Language User Interface (NLUI). Users express desired system capabilities
and developer environments in natural language. To ensure that stochastic natural language cannot
introduce operational hazards, the pipeline enforces a **Gherkin-Gated step point**:

```
[ User Request in Natural Language ]
               │
               ▼ (NLUI Intent Parser)
[ Gherkin Verification Gate ]
  Feature: Developer Workstation Provisioning
    Scenario: Enable Containerized Virtualization & KVM
      Given an x86_64 host running Fedora 44 or EL10
        And /dev/kvm is accessible with virtualization enabled in BIOS
       When role "libvirt" and role "containerd" are executed
       Then libvirtd.service must be active and enabled
        And user "b08x" must belong to group "libvirt"
        And subuid and subgid allocations must exist for rootless Podman
               │
               ▼ (Deterministic AST & Schema Compilation)
[ Ansible Task & Play Compilation ]
  - Tier 1 Variables: use_kvm: true, use_containers: true
  - Pre-flight checks: tasks/assert.yml (<1s fail-fast)
  - Playbook execution: ansible-playbook or ansible-pull
```

Through this mechanism:
- **Given** defines the mandatory precondition assertions validated by `tasks/assert.yml`.
- **When** maps to role execution, tag filters, and Tier 1 configuration flags.
- **Then** maps to post-convergence assertion checks and idempotency verification (`changed=0`).

---

## Converged Parity: Image Building vs Running Host Convergence

The platform enforces **converged parity across target footprints**. The same Ansible feature sets,
roles, and configuration invariants drive two distinct operational targets:

```
                    ┌─────────────────────────────────────────┐
                    │    Unified Feature Sets & Ansible Roles │
                    │   (common, tuning, networking, gpu...)  │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
    ┌───────────────────────────────┐         ┌───────────────────────────────┐
    │   Declarative Image Building  │         │   Live Host Convergence       │
    │      (companion osbuild)      │         │   (ansible-playbook / pull)   │
    ├───────────────────────────────┤         ├───────────────────────────────┤
    │ - ISO Installer Pipelines     │         │ - Bare-metal Workstations     │
    │ - bootc / OSTree Containers   │         │ - Server Distributions        │
    │ - Appliance & VM Disk Images  │         │ - Kiosk Appliances            │
    └───────────────────────────────┘         └───────────────────────────────┘
```

1. **Declarative Base Image & Appliance Composition (Offline Build)**:
   Via the companion [`osbuild`](https://gitlab.com/syncopatedX/osbuild) repository, the identical
   package taxonomies and role configurations are compiled into bootable ISO installers, OSTree/bootc
   container appliances, and disk images.
2. **Active Infrastructure Convergence (Online Execution)**:
   The same roles run against running bare-metal workstations, server distributions, and kiosk appliances
   via `ansible-playbook` or `ansible-pull`.

Because both targets share the same single-ownership rules, variable schemas, and package definitions,
behavior across newly baked images and live converged hosts remains 100% consistent.

---

## Controlled Reference Distilled Dataset

This repository is intentionally structured as a **controlled reference distilled dataset** for
autonomous coding agents and LLM execution pipelines:

- **Authoritative Invariants**: Autonomous agents can inspect this repository as a canonical ground truth
  for safe Linux configuration automation.
- **Vetted Domain Idioms**:
  - *Tier 1 vs Tier 2 variable separation*: Eliminates variable collision across plays.
  - *Seat-aware handlers*: Handlers in `roles/desktop_ui` query `loginctl list-sessions` to prevent
    terminating an active user's graphical seat.
  - *Single file ownership*: Exactly one role owns each file path on disk.
  - *Check-mode safety*: Pre-flight tasks and probes enforce `check_mode: false` to ensure `--check`
    dry-runs produce valid diagnostic facts.
- **Synthesizing Automation On Demand**: Autonomous agents can safely reference these vetted structures
  to synthesize new plays, modules, or roles that immediately inherit the repository's deterministic gates.

---

## The Three Layers, From the Floor Up

**OSBuild (Layer 0) is the floor.** It bakes the immutable base image—the bootc/OSTree container appliance
definition, core compiler toolchains, virtualization and container runtimes, system DNF repository configurations,
and the core kernel—and is built, never mutated.

**Ansible (Layer 1) is the machine.** It owns host-level RPMs, hardware acceleration and GPU drivers
(CUDA, Vulkan, Intel oneAPI), system Flatpaks, system CLI binaries (`/usr/local/bin/transcribe`), and
system services (`sshd`, `zram`, `libvirtd`). Its unprivileged user-space half lives in
[`roles/user`](../roles/user), which owns user toolchains: bun (`~/.bun/bin/bun`), the Go toolchain
(`~/.local/go`), and cargo crates (`~/.cargo/bin`)—idempotent by contract, so a re-run against a converged
host reports zero changes.

**Yadm (Layer 2) is the user.** It owns `$HOME`: dotfiles and Jinja2 config templates, shell env sourcing
for user toolchains (`~/.zshenv` sources `~/.cargo/env`), user Ruby gems via rbenv, user-space Flatpaks,
and the coding agent configs (`~/.claude/settings.json`, `~/.config/crush/`)—the one layer a re-image does not erase.

**Sandboxes (Fast Layer) are ephemeral.** Podman and containerd execution sandboxes provide isolated,
disposable environments for builds, tests, and untrusted code execution.

---

## Layer Ownership Principles

### 1. Single Ownership
Each package, toolchain, or configuration file must have exactly one authoritative manager. If Yadm manages
a package list (e.g. `cargo-packages.txt`, `default-gems.txt`), Ansible must not attempt parallel installation
loops; if Ansible installs a system package via DNF, OSBuild does not duplicate it unless required in the
minimal bootc image. The canonical case of violating the rule is [`failure point 2`](failure-points.md#2-one-file-one-owner):
`base` and `tuning` both templated `/etc/systemd/zram-generator.conf`—`memtotal/2` in one, `min(ram, 8192)`
in the other—and every run flapped the file between them, defeating idempotency by ownership rather than
by task logic.

### 2. No Template Clobbering
Ansible roles must never overwrite dotfiles or configurations tracked by Yadm in `$HOME`. When Ansible
drops helper configurations, it must check for existing user files or gate deployments to prevent clobbering
user customizations.

### 3. Separation of Binaries and Dotfiles
System and toolchain binaries belong in `/usr/local/bin` (provisioned by Ansible) or
`$HOME/.local/bin` / `$HOME/.cargo/bin` / `$HOME/.bun/bin` (provisioned by the unprivileged [`roles/user`](../roles/user)
toolchain tasks). Shell environments, aliases, and shell initialization belong strictly to Yadm dotfiles (`.zshrc##template.j2`).

### 4. Fail-Fast Preconditions and Check-Mode Safety
Every Ansible role frontloads assertions in `tasks/assert.yml` to fail fast (< 1s) when runtime invariants are violated:
- **Distribution & Package Manager**: Validates `ansible_os_family == 'RedHat'` and package manager in `['dnf', 'dnf5']`, ensuring verified parity across Fedora 44, AlmaLinux 10, and Rocky Linux 10.
- **Elevation**: Confirms effective root permissions (`id -u == 0`) before attempting mutations.
- **Identity Fact Propagation**: Verifies `user.name` is resolved to prevent orphan files or mismatched home directories.
- **Check-Mode Safety**: All assertions, capability probes, and stat tasks enforce `check_mode: false` so that dry-run validations (`--check`) report accurate diagnostics without halting prematurely. A converged host re-run with `--check` reports zero changes.

### 5. Two-Tier Variable Architecture
- **Tier 1 (Host & Domain Scope)**: Semantic, unprefixed Single Source of Truth keys (`user.name`, `user.home`,
  `intel_oneapi_install`, `nvidia_cuda_install`, `enable_third_party_repos`, `use_containers`, `use_kvm`)
  housed in `inventory/group_vars/` and `inventory/host_vars/`. These represent physical hardware and user identity.
- **Tier 2 (Role Scope)**: Variables defined in role `defaults/main.yml`, `vars/main.yml`, and `set_fact` must be
  role-prefixed (`<role>_*`) to maintain clean namespaces and prevent host variable leakage.
- **Registered Variables**: Variables created via `register:` must be role-prefixed (`_<role>_*`) because registered
  variables possess global host scope in Ansible and collide if left generic.

### 6. Session-Safe Handlers
Handlers must never blindly restart desktop-critical units. Handlers in `roles/desktop_ui` query
`loginctl list-sessions` to verify seat occupancy before triggering display manager restarts, avoiding
severing active Wayland sessions.

---

## Packaging Delivery Matrix

The full lookup: this is where single ownership stops being a principle and becomes a lookup—every kind of thing
has exactly one row, and the row is the owner.

| Delivery Mechanism | Target Layer | Manager / Tool | Examples | Justification / Boundary Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Base RPM Packages** | OSBuild | `osbuild` / `bootc` | `kernel`, `podman`, `gcc`, `glibc`, `cosmic-desktop` | Immutable appliance foundations. Baked at build time with DNF/DNF5 package management. |
| **Host RPM Packages** | Ansible | `ansible.builtin.dnf` (DNF / DNF5 validated) | `sox`, `tesseract-devel`, `yad`, `wl-clipboard`, `@gnome-desktop`, `@cosmic-desktop` | Dynamic host capabilities, desktop environments (GNOME & COSMIC), hardware dev libraries. Validated on DNF5 (Fedora 44) and DNF (AlmaLinux 10 / Rocky Linux 10). |
| **System Binaries** | Ansible | [`roles/common`](../roles/common) (`inxi`, `gitflow-avh`), [`playbooks/transcribe-cpp.yml`](../playbooks/transcribe-cpp.yml) (`transcribe`) | `/usr/local/bin/transcribe`, `/usr/local/bin/git-flow`, `/usr/local/bin/inxi` | Globally shared utilities requiring compilation or system-wide drop. `transcribe` is built by its opt-in standalone playbook, gated on CUDA/Vulkan GPU hardware presence. `bun` is in user space (`~/.bun/bin/bun`, owned by [`roles/user`](../roles/user)). |
| **GPU Vendor Stacks** | Ansible | [`roles/gpu`](../roles/gpu) | `intel-oneapi-*` pinned MKL/compiler set, `akmod-nvidia`, `nvidia-driver-*`, `cuda`/`cuda-devel`, `nvidia-container-toolkit` + CDI service | Optional per-host stacks gated by Tier 1 `intel_oneapi_install` / `nvidia_cuda_install`; tools and common probe only. |
| **System Flatpaks** | Ansible | [`roles/tools/tasks/flatpak.yml`](../roles/tools/tasks/flatpak.yml) | `ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy` | System-wide utility and administration GUI applications. |
| **User Flatpaks** | Yadm | `yadm/bootstrap.d/80-install-user-flatpaks.sh` | `Obsidian`, `Typora`, `Audacity`, `freac`, `Helvum`, `Podman Desktop`, `DBeaver` | User productivity, authoring, and media creation applications installed per-user. |
| **User Rust / Cargo** | Ansible + Yadm | [`roles/user`](../roles/user) (`tasks/cargo.yml`), Yadm (`bootstrap.d/20-cargo.sh` bootstrap fallback, `~/.cargo` env sourcing) | `bottom`, `choose`, `git-cliff`, `gping`, `ripgrep_all`, `sd`, `gitui`, `eza` | `roles/user` provisions crates with behavior parity from the yadm script (system-cargo-first with threshold, rustup fallback, DNF-preferred packages); the yadm script remains the bootstrap-time fallback. `~/.cargo/config.toml` and rc files stay Layer 2. |
| **User Toolchains (bun, Go) & Extensions** | Ansible | [`roles/user`](../roles/user) (`bun`, `go`, `gnome-extensions`, `vscode-extensions`) | `~/.bun/bin/bun`, `~/.local/go` (+ `~/.local/bin` symlinks), GNOME Shell extensions, VS Code extensions | Unprivileged user-space toolchain decision trees and extension lists migrated from yadm bootstrap.d; shell PATH coverage owned by Layer 2 (`~/.zshrc`, `workstation_path_dirs`). |
| **User Ruby Gems** | Yadm | `yadm/bootstrap.d/01-ruby.sh` | `pry`, `solargraph`, `ruby-lsp`, `rubocop`, `bubblezone`, `huh`, `ntcharts` | User gemsets installed against rbenv Rubies in `~/.local/bin`. |
| **Python Environments** | Ansible + Yadm | Ansible (binary), Yadm (environment) | `uv`, `python3.14` (Fedora 44) / `python3.12+` (EL 10) (Ansible); `UV_PYTHON_PREFERENCE="only-managed"` (Yadm) | Ansible installs system Python and uv runtimes; user dotfiles set shell resolution policies. |
| **Coding Agents** | Ansible + Yadm | [`playbooks/agent-harness/`](../playbooks/agent-harness/) (binaries), Yadm (config) | CLI binaries (`agy`, `claude`, `crush`, `opencode`); configs via `~/.claude/`, `~/.config/crush/` | Ansible [`playbooks/agent-harness/`](../playbooks/agent-harness/) manages binaries; Yadm manages configs and shared skills. |
| **Bootstrap Orchestration** | Yadm &rarr; Ansible | `yadm/bootstrap.d/02-ansible-pull.sh` | `ansible-pull` targeting [`local.yml`](../local.yml) | Automated orchestration bridge between Layer 2 (Yadm) and Layer 1 (Ansible). Converges host state prior to applying user configurations; skips (RC_SKIPPED) when the machine pull marker `~/.initial-firstboot` shows the host was already converged (ISO firstboot stage 1 or an earlier bootstrap). |
