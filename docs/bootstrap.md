# Workstation Bootstrap Guide

This document describes the bootstrap process for provisioning a fresh workstation across Ansible and Yadm.

## The Provisioning Taxonomy

This project enforces a strict boundary between immutable base images, host-level provisioning, and user configuration. See [docs/layering-architecture.md](layering-architecture.md) for the full taxonomy matrix:

- **OSBuild (Layer 0)**: Builds the immutable base appliance (kernel, hardware drivers, container runtimes).
- **Ansible (Layer 1)**: Manages host-level packages, hardware acceleration, system Flatpaks, system utilities (`bun`, `transcribe.cpp`), and coding agent binaries.
- **Yadm (Layer 2)**: Manages unprivileged user dotfiles, shell configuration, language version managers (`rbenv`, `rustup`), default gems, user Cargo crates, and user Flatpaks (`Obsidian`, `Typora`, media utilities).

---

## Provisioning Workflows

Depending on whether you are provisioning locally on a fresh machine or orchestrating across the inventory, two workflows are supported:

### Workflow A: Autonomous Pull Bootstrap (`local.yml`)

The root [`local.yml`](../local.yml) playbook is designed for local workstation convergence via `ansible-pull`. It implements the 15 Ansible Design Patterns:
- **Pre-flight Hardware Auto-Detection**: Dynamically probes for KVM hardware acceleration (`/dev/kvm`), graphical display target (`systemctl get-default`), and container runtime support.
- **Tag-as-Select Filtering**: Every role is tagged (`base`, `tuning`, `networking`, `containerd`, `libvirt`, `desktop`, `tools`, `system`, `virt`).
- **Check-Mode Safety**: All pre-flight probes and post-flight assessments run with `check_mode: false`.
- **Reboot Assessment**: Checks `needs-restarting -r` (EL/Fedora) and `/var/run/reboot-required` (Debian) and outputs a formatted status summary.

#### Standalone Execution
```bash
# Pull and apply from the GitLab workstation repository
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git local.yml

# Dry-run check mode
sudo ansible-pull -U https://gitlab.com/syncopatedX/workstation.git --check local.yml

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

---

### Workflow B: Interactive TUI Orchestrator (`bin/setup`)

The `bin/setup` script is an interactive TUI orchestrator that guides you through an end-to-end setup:

1. **Prerequisite Check**: Verifies `git`, `ansible-playbook`, and `gum` are available (installs via `sudo dnf` if missing).
2. **GPG Key Check**: Validates secret keys required for decrypting dotfiles secrets.
3. **Run Ansible**: Executes `ansible-playbook playbooks/site.yml -K` against the local host.
4. **Install Yadm**: Ensures `/usr/local/bin/yadm` is installed.
5. **Yadm Clone & Decrypt**: Clones your dotfiles repository and prompts for secret decryption.
6. **Yadm Bootstrap**: Runs `~/.config/yadm/bootstrap` for unprivileged toolchains and user applications.

```bash
./bin/setup
```

---

## Prerequisites

Before starting bootstrap on a fresh installation:

1. **Base system installed**: Fedora or AlmaLinux workstation installation.
2. **GPG Key Setup**: If your Yadm dotfiles use `yadm encrypt` (e.g. for SSH keys), import your private key:
   ```bash
   gpg --import private.key
   ```
3. **Network access**: Outbound HTTPS access to GitLab (`gitlab.com/syncopatedX/workstation.git`) and package repositories.
