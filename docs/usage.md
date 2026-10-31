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

## Full Provisioning

```bash
# From the repository root (defaults to GNOME desktop environment)
ansible-playbook playbooks/workstation.yml

# Provision COSMIC desktop environment instead of GNOME
ansible-playbook playbooks/workstation.yml -e desktop_ui_environment=cosmic

# Specific role only
ansible-playbook playbooks/workstation.yml --tags "tools"

# Specific role with fine-grained tags (e.g. COSMIC desktop components)
ansible-playbook playbooks/workstation.yml --tags "desktop_ui,cosmic"

# Pre-flight assertions only (fail-fast validation, no mutations)
ansible-playbook playbooks/workstation.yml --tags "assert" --check
```

## Local Pull-Based Convergence

```bash
# System layer (root)
ansible-pull -U <repo-url> --tags system local.yml

# User layer (unprivileged)
ansible-pull -U <repo-url> --tags user local.yml

# Or directly
ansible-playbook local.yml
```

## Staged Bootstrap (Fresh Machine)

Three stages, fully automated from a minimal install. See
[`bootstrap.md`](bootstrap.md) for the full lifecycle details.

1. **`scripts/bootstrap.sh`** — installs `git`, `ansible-core`, runs `dnf
   upgrade -y --refresh`, stages `syncopated-bootstrap-root.service`, reboots
2. **`scripts/syncopated-bootstrap-root.sh`** — post-reboot systemd runner
   (TimeoutSec=0) executing `ansible-pull --tags system local.yml`, writes
   completion sentinel, self-disables, reboots into graphical environment
3. **`syncopated-firstboot`** — deployed by the `common` role; triggers on first
   user login to clone dotfiles via yadm, run unprivileged user bootstrap

## Testing

```bash
# Molecule (common role: builds Fedora + AlmaLinux containers, converges twice)
molecule test

# Lint
ansible-lint

# Pre-commit
pre-commit run --all-files
```

## Vagrant VM

```bash
vagrant up fedora    # libvirt Fedora workstation VM
```
