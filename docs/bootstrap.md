# Workstation Bootstrap Guide

This document describes the bootstrap process for provisioning a fresh workstation across Ansible and Yadm. Prerequisites come first; the rest of the document tells one story — converging the machine exactly once through the same pull — and the three paths are simply where you enter it.

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

## The Provisioning Taxonomy

This project enforces a strict boundary between immutable base images (OSBuild, Layer 0), host-level provisioning (Ansible, Layer 1), and unprivileged user configuration (yadm, Layer 2). The full taxonomy and its ownership matrix live in [`layering-architecture.md`](layering-architecture.md).

---

## The Lifecycle, and Where You Enter It

All three paths below end at the same place: a converged Layer 1 and a yadm-ready Layer 2. They differ only in who starts the machine and where you stand when it happens — Path 1 enters at first console login on an ISO-built machine, Path 2 enters when an interactive user terminal already exists, and Path 3 converges the system layer only (its pull variant runs the system play alone; its local-playbook variant converges both plays from an existing clone).

The lifecycle they enter is the two-stage firstboot convergence: **stage 1** is console (tty1) system convergence — network wait, `dnf upgrade`, language toolchains, and (when the image is armed) one privileged `ansible-pull` against [`local.yml`](../local.yml), which converges Layer 1 and writes the machine pull marker `~/.initial-firstboot` (the primary workstation user's home; world-readable `root:root 0644`) — then set the default target to `graphical.target` and offer a reboot; **stage 2** fires at the first graphical login via the XDG autostart entry and offers to AUTO-RUN `yadm clone --bootstrap` (the yadm bootstrap orchestrator owns the drift preflight and the step registry), silencing itself with the per-user `~/.local/state/syncopated/firstboot-stage2.done` marker. Both stages stay runnable by name (`syncopated-firstboot --stage 1|2`); the markers gate only the automatic triggers. (The legacy `scripts/` relay — `bootstrap.sh`, `syncopated-bootstrap-root.sh`, the stage-3 `scripts/syncopated-firstboot`, and `scripts/01-ansible-pull.sh` — has been retired; stock-Fedora rebuilds now use Path 2 or Path 3.)

### Path 1: ISO Two-Stage Firstboot (Fresh Installs from an osbuild Image)

This is the fully automated lifecycle for machines installed from a Syncopated ISO (layer 0 built by the osbuild repository). The kickstart boots the installed system to `multi-user.target`, so first login happens on tty1 — no curl-pipe-bash, no staged runner.

The image already carries everything stage 1 needs:

- the 7-file firstboot suite (`/usr/local/bin/syncopated-firstboot`, `-launcher`, `-toolchains`, `/etc/xdg/autostart/syncopated-firstboot.desktop`, `/etc/profile.d/syncopated-firstboot.sh`, `syncopated-path.sh`, `rbenv.sh`);
- `/etc/syncopated-ansible-pull.conf` (`ANSIBLE_PULL_REPO=https://gitlab.com/syncopatedX/workstation.git`, `ANSIBLE_PULL_ARGS` incl. `-C development`), read by stage 1's `ansible_pull` step;
- `/etc/syncopated-user.conf` (`WORKSTATION_USER=<name>`), read by `local.yml`'s pre-flight to resolve the install-time user deterministically.

**Lifecycle Stages:**

1. **Stage 1 (tty1 system convergence — `syncopated-firstboot --stage 1`, fired by `/etc/profile.d/syncopated-firstboot.sh`)**:
   - The hook triggers only on an interactive, non-root, non-SSH login shell on `/dev/tty1`, and only while `~/.initial-firstboot` is absent (the marker lives in the primary user's home and is world-readable, so a plain `test -f` — no `sudo` on the login hot path — and nothing under the non-root-unsearchable `/root`).
   - Waits for the network, performs a full system upgrade via `sudo dnf -y upgrade --refresh`, and sets up the language toolchains (`syncopated-toolchains`).
   - Runs `sudo ansible-pull -U "$ANSIBLE_PULL_REPO" $ANSIBLE_PULL_ARGS` (skipped with `RC_SKIPPED` when the conf is missing/incomplete or `ansible-pull` is not installed). The pull converges both plays of [`local.yml`](../local.yml), deploys the same 7-file firstboot suite through `roles/user`, and — on a full-tag run — writes `~/.initial-firstboot` into the primary workstation user's home (`root:root`, `0644`, one ISO-8601 timestamp). Partial-tag runs deliberately do not write the marker.
   - Verifies the marker after a successful pull (warns when a partial-tag run left it absent), sets the default boot target to `graphical.target` when a display manager is installed, and offers a reboot when updates were installed.
2. **Stage 2 (graphical autostart — `syncopated-firstboot --stage 2`, fired by `/etc/xdg/autostart/syncopated-firstboot.desktop` via the launcher)**:
   - The launcher opens a terminal running stage 2 unless the per-user `~/.local/state/syncopated/firstboot-stage2.done` marker exists (the legacy `firstboot.done` marker from the single-stage splash also counts as done — read-compat only, so already-onboarded users are never nagged).
   - Offers `Run yadm setup now` / `Show commands` / `Skip for this machine`. Running installs yadm when missing and executes exactly `yadm clone --bootstrap $DOTFILES_URL` — drift preflight, the bootstrap step registry, and retry/skip/abort handling belong to the yadm orchestrator (Layer 2), never reimplemented here.
   - Writing the stage-2 marker (completed or declined) silences only the autostart trigger; `syncopated-firstboot --stage 2` by name always shows the offer and commands.

---

### Path 2: Autonomous Yadm Bootstrap (Full Stack Convergence)

For systems with an interactive user terminal already configured, initiating bootstrap from Yadm orchestrates both Layer 1 (system) and Layer 2 (user space). The levels invert for one beat: you clone your dotfiles, and before a single dotfile lands, the dotfiles' own bootstrap script reaches down and pulls the system layer into the state your user configuration presupposes — the top of the stack becomes the orchestrator of the bottom.

```bash
# 1. Clone your personal dotfiles repository via Yadm
yadm clone https://github.com/<your-username>/dotfiles.git

# 2. Execute Yadm bootstrap
yadm bootstrap
```

**Execution Flow:**
1. **Clone**: Yadm pulls dotfiles and bootstrap scripts to `~/.config/yadm/`.
2. **Layer 1 Bridge (`bootstrap.d/02-ansible-pull.sh`)**: Yadm executes the consolidated `02-ansible-pull` step, which CONDITIONALLY invokes `ansible-pull` targeting [`local.yml`](../local.yml) — the step checks the machine pull marker at the top of its `main()` (plain `test -f ~/.initial-firstboot`, no sudo — the marker is world-readable in the primary user's home, and `/root` is unstat-able by non-root users): when it exists (the machine was already converged through stage 1 or an earlier bootstrap) the step logs the skip and returns `RC_SKIPPED`; when absent it runs the single privileged pull. `SYNCOPATED_ANSIBLE_PULL_FORCE=1` re-converges by name regardless of the marker.
3. **Layer 1 Convergence**: Ansible discovers local hardware capabilities (KVM, GPU CUDA/Vulkan, desktop target), executes fail-fast assertions, installs host RPMs (via DNF/DNF5), configures system services, Flatpaks, and host binaries — and, through the `user` role, deploys the same 7-file firstboot suite an ISO path plants, then writes `~/.initial-firstboot` after a full-tag run.
4. **Layer 2 Convergence**: Control returns to Yadm to unpack dotfiles templates, install user Rust tools via `cargo`, user gems via `rbenv`, and user-space Flatpaks.

---

### Path 3: Standalone Local Convergence (Host Layer 1 Only)

When you need to converge the host system without touching user dotfiles, run [`local.yml`](../local.yml) directly:

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

The root [`local.yml`](../local.yml) playbook is designed for local workstation convergence via `ansible-pull`. It implements the 15 Ansible Design Patterns and is structured into two decoupled plays.

**Play 1 (System Provisioning — `become: true`, `--tags system`)** probes before it mutates: KVM virtualization via `/dev/kvm`, the graphical display target via `systemctl get-default`, container runtime support, and GPU hardware accelerators — CUDA via `/dev/nvidia*` / PCI `0x10de`, Vulkan physical GPUs via `vulkaninfo` / DRM render nodes. The resulting facts (`has_cuda_device`, `has_vulkan_device`) report GPU availability to interested consumers; transcribe.cpp is now built by the opt-in standalone [`playbooks/transcribe-cpp.yml`](../playbooks/transcribe-cpp.yml) playbook, which runs its own probes and honors these exported facts when invoked. Every role then executes frontloaded fail-fast assertions (`tasks/assert.yml`: platform compatibility, package managers, effective root permissions `id -u == 0`, identity prerequisites), targeted or skipped via `--tags assert` / `--skip-tags assert` or gated individually via `<role>_assert_enabled: true/false`.

The desktop role is enabled by default on workstations (`auto_enable_desktop: true`): GDM is configured for native Wayland (`WaylandEnable=true` in `/etc/gdm/custom.conf`), the default target is promoted to `graphical.target`, and `gdm.service` is managed. All pre-flight probes and post-flight assessments run with `check_mode: false`, and the play closes with a reboot assessment — `needs-restarting -r` (EL/Fedora) and `/var/run/reboot-required` (Debian) — reported as a formatted status summary. Every role is tagged for Tag-as-Select filtering: `common`, `tuning`, `gpu`, `networking`, `containerd`, `libvirt`, `desktop`, `tools`, `system`, `virt`.

**Play 2 (User Provisioning — `become: false`, `--tags user`)** executes strictly as the unprivileged user without requesting `sudo` credentials: it sets up user directories, resolves paths, and installs Python toolchains via `uv python install {{ user_uv_python_version }}`.

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
Yadm's bootstrap pipeline executes the consolidated `bootstrap.d/02-ansible-pull.sh` step. It is conditional on the machine pull marker `~/.initial-firstboot` (primary workstation user's home):
- When the marker exists, the step logs `firstboot ansible-pull already completed; skipping` (naming the marker path) and returns `RC_SKIPPED` (2) — bootstrap continues its remaining steps.
- When the marker is absent, the step computes hardware- and desktop-aware default tags (`gpu` only with a GPU, `libvirt` only with KVM, `desktop_ui,desktop` only on a graphical desktop) and runs one privileged `ansible-pull` (`--ask-become-pass`) against `https://gitlab.com/syncopatedX/workstation.git` / `local.yml`; override the tag CSV with `SYNCOPATED_ANSIBLE_TAGS`, force the desktop environment with `SYNCOPATED_DESKTOP_UI_ENVIRONMENT`.
- `SYNCOPATED_ANSIBLE_PULL_FORCE=1` runs the pull despite the marker (re-converge by name); `SYNCOPATED_ANSIBLE_PULL_FIRSTBOOT_MARKER` overrides the marker path for testing.

Choosing which yadm bootstrap steps run:
- On a terminal, `yadm bootstrap` shows a multi-select menu of every step (preflight, shell, decrypt, alternates and each `bootstrap.d` script). All steps start selected; unselected steps are reported as "not run".
- `yadm bootstrap --all` skips the menu and runs every step. Without a terminal the menu is also skipped.
- `yadm bootstrap --only cargo,ruby` runs just the named steps; an unknown name exits with status 2 and lists the valid names.
- Each installable item (crate, gem, flatpak, VS Code extension, toolchain) runs under a spinner titled with its readable name. Installer output goes to `~/.bootstrap.log` and is shown only when the item fails.
- When a selected step needs `sudo`, bootstrap runs `sudo -v` once before the first spinner.

---

### Workflow B: Push Orchestration (`playbooks/workstation.yml`)

For remote orchestration across an inventory fleet or centralized workstation management, use [`playbooks/workstation.yml`](../playbooks/workstation.yml).

The playbook executes across four structured plays targeting the `workstations` group:
1. **System Provisioning and Common Configuration**: Runs [`roles/common`](../roles/common) with elevated privileges (`become: true`), performs fact gathering, handles sudoers `requiretty` adjustments, and ensures system release symlinks.
2. **System Configuration**: Applies system roles (`tuning`, `networking`, `containerd`, `desktop`, `libvirt`) with facts gathered as unprivileged connection user.
3. **Host Tools**: Runs [`roles/tools`](../roles/tools) to configure the opt-in Visual Studio Code IDE, system Flatpaks, and input-remapper; transcribe.cpp is built by the standalone [`playbooks/transcribe-cpp.yml`](../playbooks/transcribe-cpp.yml) playbook, and coding agent CLIs by [`playbooks/agent-harness/`](../playbooks/agent-harness/).
4. **User Workstation Setup**: Executes [`roles/user`](../roles/user) as the unprivileged connection user (`become: false`) with user path environments — after Host Tools, mirroring `local.yml`'s tools-then-user ordering, so user-space toolchains (bun, Go, cargo, GNOME/VS Code extensions) build against the freshly installed system packages.

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

A dedicated Fedora workstation definition is integrated into the [`Vagrantfile`](../Vagrantfile) using libvirt/KVM for isolated local test cycles:

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
