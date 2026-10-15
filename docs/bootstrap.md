# Workstation Bootstrap Guide

This document describes the bootstrap process for provisioning a fresh workstation across Ansible and Yadm.

## The Provisioning Taxonomy

This project enforces a strict boundary between immutable base images, host-level provisioning, and user configuration. See [docs/layering-architecture.md](file:///home/b08x/WorkspaceV3/Syncopated/workstation/docs/layering-architecture.md) for the full taxonomy matrix:

- **OSBuild (Layer 0)**: Builds the immutable base appliance (kernel, hardware drivers, container runtimes).
- **Ansible (Layer 1)**: Manages host-level packages, hardware acceleration, system Flatpaks, system utilities (`bun`, GPU-accelerated `transcribe.cpp`), and coding agent binaries.
- **Yadm (Layer 2)**: Manages unprivileged user dotfiles, shell configuration, language version managers (`rbenv`, `rustup`), default gems, user Cargo crates, and user Flatpaks (`Obsidian`, `Typora`, media utilities).

---

## Fresh Machine Quickstart

For a brand-new installation, choose between two primary convergence paths:

### Path 1: Autonomous Yadm Bootstrap (Full Stack Convergence)

This is the recommended path for end-to-end workstation onboarding. Initiating bootstrap from Yadm orchestrates both Layer 1 (system) and Layer 2 (user space) in a single sequence:

```bash
# 1. Clone your personal dotfiles repository via Yadm
yadm clone https://github.com/<your-username>/dotfiles.git

# 2. Execute Yadm bootstrap (or automate unattended with SYNCOPATED_ANSIBLE_PULL=yes)
yadm bootstrap
```

**Execution Flow:**
1. **Clone**: Yadm pulls dotfiles and bootstrap scripts to `~/.config/yadm/`.
2. **Layer 1 Bridge (`01-ansible-pull.sh`)**: As its first bootstrap action, Yadm executes `01-ansible-pull.sh`, which invokes `sudo ansible-pull` targeting [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml).
3. **Layer 1 Convergence**: Ansible discovers local hardware capabilities (KVM, GPU CUDA/Vulkan, desktop target), executes fail-fast assertions, installs host RPMs (via DNF/DNF5), configures system services, Flatpaks, and host binaries.
4. **Layer 2 Convergence**: Control returns to Yadm to unpack dotfiles templates, install user Rust tools via `cargo`, user gems via `rbenv`, and user-space Flatpaks.

### Path 2: Standalone Local Convergence (Host Layer 1 Only)

When you need to converge the host without touching user dotfiles, run [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) directly:

```bash
# Autonomous pull from git repository
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git local.yml

# Or converge directly from an existing cloned repository
sudo ansible-playbook -i localhost, -c local local.yml
```

---

## Validation & Dry-Run Operations

Before executing changes on a live system, you can validate system compatibility and simulate state transitions:

### 1. Fail-Fast Assertion Checks (`< 1s`)

Execute pre-flight assertions across all roles without mutating any files or packages:

```bash
# Via ansible-pull
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --tags assert --check local.yml

# Via local playbook
sudo ansible-playbook -i localhost, -c local --tags assert --check local.yml
```

These assertions validate:
- Supported distribution: Fedora 44, AlmaLinux 10, Rocky Linux 10 (`RedHat` family).
- Package manager presence: DNF or DNF5.
- Elevation: Effective root privilege (`id -u == 0`).
- Identity: Workstation username resolution (`user.name`).

### 2. Full Dry-Run Check Mode

Simulate full playbook convergence to verify idempotency and see pending changes:

```bash
# Check-mode dry run via ansible-pull
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --check local.yml

# Check-mode dry run locally
sudo ansible-playbook -i localhost, -c local --check local.yml
```

---

## Provisioning Workflows

Depending on whether you are provisioning locally on a fresh machine or orchestrating across the inventory, two workflows are supported:

### Workflow A: Autonomous Pull Bootstrap (`local.yml`)

The root [`local.yml`](../local.yml) playbook is designed for local workstation convergence via `ansible-pull`. It implements the 15 Ansible Design Patterns:
- **Pre-flight Hardware Auto-Detection**: Dynamically probes for KVM virtualization (`/dev/kvm`), graphical display target (`systemctl get-default`), container runtime support, and GPU hardware accelerators (CUDA via `/dev/nvidia*` / PCI `0x10de`, and Vulkan physical GPUs via `vulkaninfo` / DRM render nodes). Hardware facts (`has_cuda_device`, `has_vulkan_device`, `auto_enable_transcribe`) dynamically gate GPU-dependent tools like `transcribe.cpp`.
- **Fail-Fast Precondition Assertions**: Every role executes frontloaded pre-flight assertions (`tasks/assert.yml`) validating platform compatibility, package managers, effective root permissions (`id -u == 0`), and identity prerequisites before attempting host mutations. Can be targeted or skipped via `--tags assert` / `--skip-tags assert`, or gated individually via `<role>_assert_enabled: true/false`.
- **Tag-as-Select Filtering**: Every role is tagged (`base`, `tuning`, `networking`, `containerd`, `libvirt`, `desktop`, `tools`, `system`, `virt`).
- **Check-Mode Safety**: All pre-flight probes and post-flight assessments run with `check_mode: false`.
- **Reboot Assessment**: Checks `needs-restarting -r` (EL/Fedora) and `/var/run/reboot-required` (Debian) and outputs a formatted status summary.

#### Standalone Execution
```bash
# Pull and apply from the GitLab workstation repository
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git local.yml

# Dry-run check mode
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --check local.yml

# Validate prerequisites across all roles (dry-run pre-flight check)
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --tags assert --check local.yml

# Selective execution (e.g. skip virtualization)
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --skip-tags virt local.yml
```

#### Integrated with Yadm Bootstrap
Yadm's bootstrap pipeline executes `01-ansible-pull.sh` as its first step. It is an optional, prompted step:
- Prompts with `gum confirm` in interactive terminals.
- Can be automated via environment variables:
  ```bash
  SYNCOPATED_ANSIBLE_PULL=yes yadm bootstrap
  ```
- Pulls from `https://gitlab.com/syncopatedX/workstation.git` with `ANSIBLE_STDOUT_CALLBACK=default`.

Choosing which yadm bootstrap steps run:
- On a terminal, `yadm bootstrap` shows a multi-select menu of every step (preflight, shell, decrypt, alternates and each `bootstrap.d` script). All steps start selected; unselected steps are reported as "not run".
- `yadm bootstrap --all` skips the menu and runs every step. Without a terminal the menu is also skipped.
- `yadm bootstrap --only cargo,ruby` runs just the named steps; an unknown name exits with status 2 and lists the valid names.
- Each installable item (crate, gem, flatpak, VS Code extension, toolchain) runs under a spinner titled with its readable name. Installer output goes to `~/.bootstrap.log` and is shown only when the item fails.
- When a selected step needs `sudo`, bootstrap runs `sudo -v` once before the first spinner.

---

### Workflow B: Push Orchestration (`playbooks/workstation.yml`)

For remote orchestration across an inventory fleet or centralized workstation management, use [`playbooks/workstation.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/playbooks/workstation.yml).

The playbook executes across four structured plays targeting the `workstations` group:
1. **System Provisioning and Base Configuration**: Runs [`roles/base`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/base) with elevated privileges (`become: true`), performs fact gathering, handles sudoers `requiretty` adjustments, and ensures system release symlinks.
2. **System Configuration**: Applies system roles (`tuning`, `networking`, `containerd`, `desktop`, `libvirt`) with facts gathered as unprivileged connection user.
3. **User Workstation Setup**: Executes [`roles/user`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/user) as the unprivileged connection user (`become: false`) with user path environments.
4. **Host Tools and Coding Agent Utilities**: Runs [`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools) to configure system CLI binaries (`bun`, `transcribe.cpp`) and coding agent harnesses.

```bash
# Push orchestration across inventory
ansible-playbook -i inventory/hosts playbooks/workstation.yml -K

# Push orchestration in dry-run mode
ansible-playbook -i inventory/hosts playbooks/workstation.yml -K --check

# Push pre-flight assertion check only
ansible-playbook -i inventory/hosts playbooks/workstation.yml -K --tags assert --check
```

---

## Prerequisites

Before starting bootstrap on a fresh installation:

1. **Supported Operating System**:
   - Fedora 44 (Workstation / Branched / Rawhide with DNF5).
   - AlmaLinux 10 or Rocky Linux 10 (Enterprise Linux 10 with DNF).
2. **Automation Runtimes & Tooling**:
   - Python: Python 3.14 (Fedora 44) or Python 3.12+ (Enterprise Linux 10).
   - Ansible: `ansible-core` >= 2.15 (verified up to 2.20).
   - Package Manager: DNF or DNF5.
3. **Elevation & Identity**:
   - User account with passwordless or standard `sudo` access.
   - `user.name` defined in inventory (`inventory/group_vars/all.yml`) or resolved via `workstation_user`.
4. **GPG Key Setup**: If your Yadm dotfiles use `yadm encrypt` (e.g. for SSH keys), import your private key:
   ```bash
   gpg --import private.key
   ```
5. **Network Access**: Outbound HTTPS access to GitLab (`gitlab.com/syncopatedX/workstation.git`) and distribution package repositories.
