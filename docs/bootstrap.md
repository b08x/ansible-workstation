# Workstation Bootstrap Guide

This document describes the bootstrap process for provisioning a fresh workstation using Ansible and yadm.

## The Ansible/YADM Boundary

This project enforces a strict boundary between system-level and user-level configuration:
- **Ansible** handles system-level provisioning (packages, services, repositories, system config). It must be run on the system.
- **YADM** handles user-level dotfiles and user-specific tools (NPM globals, cargo, pipx, VS Code extensions, shell config). Its bootstrap script is self-contained.

## Prerequisites

Before running the `bin/setup` script on a fresh ISO install, ensure:

1. **Base system is installed:** You should have a working Fedora or AlmaLinux installation.
2. **GPG Key Setup:** If your yadm dotfiles use `yadm encrypt` (e.g. for SSH keys), you MUST have your GPG private key available to decrypt them.
   - If you have your GPG key backed up, import it first: `gpg --import private.key`
   - Without the GPG key, `bin/setup` will warn you and `yadm decrypt` will fail.
3. **SSH Keys for YADM (optional):** If you clone yadm via SSH, you need your SSH keys. Since yadm typically manages your SSH keys encrypted with GPG, it's a chicken-and-egg problem. You can clone the repo using HTTPS first, decrypt the SSH keys via GPG, and then change the remote to SSH.

## Using `bin/setup`

The `bin/setup` script is a TUI orchestrator that guides you through the process:

1. **Prereq check** — Verifies `git`, `ansible-playbook`, and `gum` are available (installs via `sudo dnf` if missing).
2. **GPG key check** — Warns if no GPG key exists.
3. **Run Ansible** — Executes `ansible-playbook playbooks/site.yml` to provision the system. You will be prompted for your `sudo` password.
4. **Install YADM** — Downloads and installs yadm to `/usr/local/bin/yadm` if not present.
5. **YADM Clone** — Asks for your dotfiles repository URL and clones it.
6. **YADM Decrypt** — Prompts to decrypt your dotfiles secrets (requires GPG key).
7. **YADM Bootstrap** — Runs your dotfiles' `~/.config/yadm/bootstrap` script for user-level setup.

To start the process, run:
```bash
./bin/setup
```
