# Usage

How to run this repository: prerequisites, provisioning commands, bootstrap,
testing, and the Vagrant VM. For the project overview, see
[`overview.md`](overview.md). For the conventions that govern changes,
see [`conventions.md`](conventions.md).

---

## Prerequisites

- ansible-core >= 2.15 (verified on 2.18–2.20)
- Python 3.12+ (3.14 on Fedora 44)
- Ruby 4.0.4+ and Bundler (`bundle install` for repository Ruby tooling, analysis gems, and TUI monitoring)
- Root (uid 0) for the system layer — pre-flight assertions fail fast otherwise
- x86_64 architecture (the tools role pins linux-amd64/x64 upstream binaries)
- Target: Fedora 44, AlmaLinux 10, or Rocky Linux 10 (verified); pre-flight
  assertions also accept RHEL and CentOS, but those are not claimed as tested
  targets
- DNF or DNF5 package manager

## Look Before You Leap

Run this first, and before every full run: it executes every role's fail-fast
assertions and mutates nothing.

```bash
# Pre-flight assertions only (fail-fast validation, no mutations)
ansible-playbook playbooks/workstation.yml --tags "assert" --check
```

## Converge

With the assertions green, converge the host — the run defaults to headless (`desktop_environment: none` in `inventory/group_vars/all.yml`); pass `-e desktop_environment=gnome|cosmic|sway` to select a desktop environment, or target a single role or fine-grained tags.

```bash
# From the repository root (defaults to headless base; desktop_environment: none)
ansible-playbook playbooks/workstation.yml

# Provision GNOME desktop environment
ansible-playbook playbooks/workstation.yml -e desktop_environment=gnome

# Provision COSMIC desktop environment
ansible-playbook playbooks/workstation.yml -e desktop_environment=cosmic

# Specific role only
ansible-playbook playbooks/workstation.yml --tags "tools"

# Desktop stack roles with fine-grained tags
ansible-playbook playbooks/workstation.yml --tags "theme,gnome,cosmic,sway"
```

## Stay Converged

On a machine already under management, converge from the repository itself:
pull-based, root for the system layer, unprivileged for the user layer.

```bash
# System layer (root)
ansible-pull -U <repo-url> --tags system local.yml

# User layer (unprivileged)
ansible-pull -U <repo-url> --tags user local.yml

# Or directly
ansible-playbook local.yml
```

## Start From Bare Metal

A fresh machine converges itself through the two-stage firstboot flow, fully
automated from a Syncopated ISO or a stocked install — the full lifecycle is
in [`bootstrap.md`](bootstrap.md).

1. **Stage 1 — `syncopated-firstboot --stage 1`** (tty1 login hook
   `/etc/profile.d/syncopated-firstboot.sh`, fired while
   `~/.initial-firstboot` is absent) — waits for the network, runs
   `dnf upgrade -y --refresh`, sets up language toolchains, and runs the armed
   `ansible-pull` against `local.yml` when the image carries
   `/etc/syncopated-ansible-pull.conf`; the pull converges the system layer
   and writes `~/.initial-firstboot`, then the stage sets the default
   target to `graphical.target` and offers a reboot
2. **Stage 2 — `syncopated-firstboot --stage 2`** (XDG autostart launcher at
   the first graphical login, gated on the per-user
   `~/.local/state/syncopated/firstboot-stage2.done` marker) — offers to
   auto-run `yadm clone --bootstrap`, delegating drift preflight and the
   bootstrap step registry to the yadm orchestrator

On a machine that never saw the ISO flow, `yadm bootstrap` runs the same
privileged pull through `bootstrap.d/02-ansible-pull.sh` (conditional on the
same marker), so both paths converge exactly once.

## Test Your Changes

Before you commit, verify the change the way the repository verifies itself.

```bash
# Molecule (common role: builds Fedora + AlmaLinux containers, converges twice)
molecule test

# Lint
ansible-lint

# Pre-commit
pre-commit run --all-files
```

For isolated convergence testing, the Vagrant VM is a libvirt/KVM Fedora
workstation; the `FEDORA_BOX` override for custom or newer images is documented
in [`bootstrap.md`](bootstrap.md).

```bash
vagrant up fedora    # libvirt Fedora workstation VM
```
