# Workstation Bootstrap Guide

This document describes the bootstrap process for provisioning a fresh workstation across Ansible and Yadm.

## The Provisioning Taxonomy

This project enforces a strict boundary between immutable base images, host-level provisioning, and user configuration. See [docs/layering-architecture.md](file:///home/b08x/WorkspaceV3/Syncopated/workstation/docs/layering-architecture.md) for the full taxonomy matrix:

- **OSBuild (Layer 0)**: Builds the immutable base appliance (kernel, hardware drivers, container runtimes).
- **Ansible (Layer 1)**: Manages host-level packages, hardware acceleration, system Flatpaks, system utilities (`bun`, GPU-accelerated `transcribe.cpp`), and coding agent binaries.
- **Yadm (Layer 2)**: Manages unprivileged user dotfiles, shell configuration, language version managers (`rbenv`, `rustup`), default gems, user Cargo crates, and user Flatpaks (`Obsidian`, `Typora`, media utilities).

---

## Fresh Machine Quickstart

For a brand-new installation, choose between three primary convergence paths:

### Path 1: Staged Bootstrap Lifecycle (Recommended for Fresh / Minimal Installs)

This is the fully automated, multi-stage lifecycle designed for bootstrapping bare-metal machines, cloud images, or minimal VM installations from scratch:

```bash
# 1. Download and run the standalone Stage 1 bootstrapper as root
curl -fsSL https://gitlab.com/syncopatedX/workstation/-/raw/development/scripts/bootstrap.sh | sudo bash
```

**Lifecycle Stages:**
1. **Stage 1 (Initial Setup & Upgrade — `scripts/bootstrap.sh`)**:
   - Validates root elevation and environment.
   - Installs minimal bootstrapping dependencies (`git`, `ansible-core`, `ansible-collection-ansible-posix`, `ansible-collection-community-general`, `python3-dnf`, `python3-rich`).
   - Performs a full system upgrade via `dnf upgrade -y --refresh`.
   - Writes the Stage 2 runner (`/usr/local/sbin/syncopated-bootstrap-root.sh`) and stages a one-shot systemd service unit (`/etc/systemd/system/syncopated-bootstrap-root.service`) configured with `TimeoutSec=0` / `TimeoutStartSec=0` to prevent timeouts during extensive package transactions.
   - Enables `syncopated-bootstrap-root.service` and triggers system reboot.
2. **Stage 2 (Root System Provisioning — `scripts/syncopated-bootstrap-root.sh`)**:
   - Executes automatically on reboot before display manager or login prompts.
   - Runs `ansible-pull` targeting [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) with `--tags system`.
   - Discovers hardware capabilities, installs base packages, tunes system parameters, configures networking, container runtimes, tools, and the GNOME desktop with native Wayland GDM, setting the default target to `graphical.target`.
   - On success, writes completion marker `/var/log/syncopated-stage2.done`, self-disables `syncopated-bootstrap-root.service`, and reboots into the graphical greeter.
3. **Stage 3 (User Onboarding & Dotfiles — `syncopated-firstboot`)**:
   - Deployed at the system level by [`roles/base`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/base) (`/usr/local/bin/syncopated-firstboot`).
   - Hooks into first user login via `/etc/xdg/autostart/syncopated-firstboot.desktop` (graphical session) or `/etc/profile.d/syncopated-firstboot.sh` (terminal session).
   - Clones dotfiles using the native `yadm` package from the Syncopated COPR and executes unprivileged bootstrap hooks (`local.yml --tags user`) without prompting for `sudo`.
   - Writes the sentinel `~/.local/state/syncopated/firstboot.done` when complete.

---

### Path 2: Autonomous Yadm Bootstrap (Full Stack Convergence)

For systems with an interactive user terminal already configured, initiating bootstrap from Yadm orchestrates both Layer 1 (system) and Layer 2 (user space):

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

---

### Path 3: Standalone Local Convergence (Host Layer 1 Only)

When you need to converge the host system without touching user dotfiles, run [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) directly:

```bash
# Autonomous pull from git repository (system play only)
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --tags system local.yml

# Or converge both system and user plays from an existing cloned repository
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

The root [`local.yml`](../local.yml) playbook is designed for local workstation convergence via `ansible-pull`. It implements the 15 Ansible Design Patterns and is structured into two decoupled plays:

1. **Play 1: System Provisioning (Root Privileged — `become: true`, `--tags system`)**:
   - **Pre-flight Hardware Auto-Detection**: Dynamically probes for KVM virtualization (`/dev/kvm`), graphical display target (`systemctl get-default`), container runtime support, and GPU hardware accelerators (CUDA via `/dev/nvidia*` / PCI `0x10de`, and Vulkan physical GPUs via `vulkaninfo` / DRM render nodes). Hardware facts (`has_cuda_device`, `has_vulkan_device`, `auto_enable_transcribe`) dynamically gate GPU-dependent tools like `transcribe.cpp`.
   - **Fail-Fast Precondition Assertions**: Every role executes frontloaded pre-flight assertions (`tasks/assert.yml`) validating platform compatibility, package managers, effective root permissions (`id -u == 0`), and identity prerequisites before attempting host mutations. Can be targeted or skipped via `--tags assert` / `--skip-tags assert`, or gated individually via `<role>_assert_enabled: true/false`.
   - **Desktop & Display Manager**: Enables the desktop role by default on workstations (`auto_enable_desktop: true`), configures GDM for native Wayland (`WaylandEnable=true` in `/etc/gdm/custom.conf`), promotes the default target to `graphical.target`, and manages `gdm.service`.
   - **Tag-as-Select Filtering**: Every role is tagged (`base`, `tuning`, `networking`, `containerd`, `libvirt`, `desktop`, `tools`, `system`, `virt`).
   - **Check-Mode Safety**: All pre-flight probes and post-flight assessments run with `check_mode: false`.
   - **Reboot Assessment**: Checks `needs-restarting -r` (EL/Fedora) and `/var/run/reboot-required` (Debian) and outputs a formatted status summary.

2. **Play 2: User Provisioning (Unprivileged User Space — `become: false`, `--tags user`)**:
   - Executes strictly as the unprivileged user without requesting `sudo` credentials.
   - Sets up user directories, resolves paths, and installs Python toolchains via `uv python install {{ user_uv_python_version }}`.

#### Standalone Execution
```bash
# Pull and apply system configuration (root privileged)
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --tags system local.yml

# Pull and apply user space configuration (unprivileged)
ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --tags user local.yml

# Dry-run check mode across all plays
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

### Workflow C: Local Virtualization Testing (`Vagrantfile`)

A dedicated Fedora workstation definition is integrated into [`Vagrantfile`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/Vagrantfile) using libvirt/KVM for isolated local test cycles:

```bash
# Start and bootstrap the Fedora workstation test VM
vagrant up fedora

# Re-run Ansible convergence inside the VM
vagrant provision fedora

# Target specific tags or check mode during provisioning
ANSIBLE_TAGS="system" vagrant provision fedora
ANSIBLE_CHECK=1 vagrant provision fedora

# Connect to the running test VM
vagrant ssh fedora
```

The Fedora VM defaults to `fedora/41-cloud-base` and can be pointed at custom or newer images by exporting `FEDORA_BOX` (e.g. `FEDORA_BOX="fedora/rawhide-cloud-base"` or custom build). Pre-installed prerequisites, sudo permissions, SSH authorized keys, and SPICE graphics are automatically configured for graphical and headless testing.

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
