<div align="center">

# Syncopated Workstation

An Ansible control repository provisioning Fedora 44 / AlmaLinux 10 / Rocky Linux 10
workstations. Ten roles. ansible-core >= 2.15, Python 3.12+ (3.14 aligned), x86_64, root required.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15%20(verified%202.18--2.20)-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![python](https://img.shields.io/badge/python-3.14%20%7C%203.12%2B-blue.svg)](https://www.python.org/)
[![Fedora](https://img.shields.io/badge/Fedora-44-294172.svg)](https://fedoraproject.org/)
[![AlmaLinux](https://img.shields.io/badge/AlmaLinux-10-blue.svg)](https://almalinux.org/)
[![Rocky Linux](https://img.shields.io/badge/Rocky%20Linux-10-green.svg)](https://rockylinux.org/)
[![dnf5](https://img.shields.io/badge/dnf5-validated-blueviolet.svg)](https://github.com/rpm-software-management/dnf5)
[![molecule](https://img.shields.io/badge/molecule-tested-blue.svg)](https://github.com/ansible-community/molecule)
[![ansible-lint](https://img.shields.io/badge/ansible--lint-enforced-black.svg)](https://github.com/ansible/ansible-lint)
[![yadm](https://img.shields.io/badge/yadm-dotfiles-blue.svg)](https://yadm.io/)
[![libvirt](https://img.shields.io/badge/libvirt%2FKVM-enabled-red.svg)](https://libvirt.org/)
[![Vagrant](https://img.shields.io/badge/Vagrant-libvirt-1867F0.svg)](https://www.vagrantup.com/)

</div>

---

Ten Ansible roles converge a Fedora 44 / AlmaLinux 10 / Rocky Linux 10 x86_64 host into a
workstation. The machine is built in three layers, and each layer owns exactly one thing:
Layer 0 is an immutable OSBuild base image, composed in a companion repository; Layer 1
is this repository — Ansible orchestration for everything the host itself is; Layer 2 is
yadm, your dotfiles, the one layer a re-image does not erase.
[`docs/overview.md`](docs/overview.md) is the full structural tour;
[`docs/layering-architecture.md`](docs/layering-architecture.md) covers the layer model
and its strict ownership boundaries.

The pipeline has a deliberate stopping point, and it is the part I find most worth
understanding: the pristine checkpoint. The machine converges itself and then stops just
before the part that is yours — build defaults are generate-only, and on first login
`syncopated-firstboot` prompts for the dotfiles repository and validates it with
`git ls-remote` before cloning anything.
[`docs/end-to-end-validation.md`](docs/end-to-end-validation.md) traces a single request
from spec sentence to converged host, with per-stage evidence calibration.

The repository was built by AI coding agents across 512 sessions over nine months, and
the failure patterns from those sessions are encoded as this repo's conventions — which
now govern the agents that extend it. [`docs/build-process.md`](docs/build-process.md) is
that history; [`docs/failure-points.md`](docs/failure-points.md) records the 22 real
build failures and the pattern each one taught.

Read this page in one of two ways. If you are the human owner, read top to bottom: the
sections run from your first command to a full picture of the machine you are about to
live inside. If you are an AI coding agent, skim down to [The Map](#the-map) for exact
paths, and treat [`AGENTS.md`](AGENTS.md) as the authoritative hard-rules list before
you edit anything. The corpus states its own evidence rules openly — how it sources
claims and labels its uncertainty is documented in
[`docs/audit-notes.md`](docs/audit-notes.md).

## Converge a host in two commands

Prerequisites: `ansible-core >= 2.15` (verified 2.18–2.20), Python 3.12+ (3.14 on Fedora
44), x86_64, and root for the system layer.

```bash
# Pre-flight: run every role's assertions, mutate nothing
ansible-playbook playbooks/workstation.yml --tags assert --check

# Full provisioning
ansible-playbook playbooks/workstation.yml
```

The pre-flight runs every role's `tasks/assert.yml` — platform, package manager, init
manager, effective root, identity variables — and mutates nothing; a failed assertion
stops the run in under a second. The full run is idempotent by contract: on a converged
host it reports zero changes. Fail fast, mutate never is the house style. Tags,
single-role runs, `--check`, Vagrant, and testing are in
[`docs/usage.md`](docs/usage.md).

## The layers, and who owns what

Layer 0 is the floor: an OSBuild-built immutable base image, with declarative blueprints
composed in the companion [`osbuild`](https://gitlab.com/syncopatedX/osbuild) repository.
Layer 1 is this repository: Ansible converging the host through ten roles — `common`,
`containerd`, `desktop_ui`, `libvirt`, `nas`, `networking`, `tools`, `tts`, `tuning`,
`user` — idempotent by contract. Layer 2 is yadm: the user's dotfiles, cloned on first
login and owned by the user forever after.

The boundaries are strict by design: single ownership, no template clobbering,
separation of binaries and dotfiles, and fail-fast preconditions — every role ships
`tasks/assert.yml`, gated by `<role>_assert_enabled | default(true) | bool`, tagged
`[<role>, assert, always]`, and runnable standalone via `--tags assert` in under a
second.

The Layer 1 surface is five entry points:

- [`local.yml`](local.yml) — the root-level `ansible-pull` entry point for autonomous
  local convergence (`ansible-pull -U <repo-url> --tags system local.yml`; run
  instructions in its header comments and [`docs/usage.md`](docs/usage.md)). Two
  decoupled plays: system provisioning (`become: true`, `--tags system`) with pre-flight
  hardware auto-detection — KVM via `/dev/kvm`, graphical display target, containers,
  CUDA/Vulkan GPUs — plus fail-fast assertions and reboot assessment; and user
  provisioning (`become: false`, `--tags user`) with uv-managed Python.
- [`playbooks/workstation.yml`](playbooks/workstation.yml) — full multi-host
  provisioning; imports [`playbooks/repositories.yml`](playbooks/repositories.yml) (DNF
  configuration, repository setup, package updates) first, then targets the
  `workstations` group (tinybot, gir).
- [`playbooks/nas.yml`](playbooks/nas.yml) — NAS services (NFSv4, Samba, Rsync,
  firewalld) against `hosts: all`.
- [`playbooks/tts.yml`](playbooks/tts.yml) — Whisper TTS against
  `hosts: workstations`.

## From bare metal to logged in

Convergence means running the playbooks until the host matches its declared state. The
staged bootstrap gets a bare machine there in three stages. Stage 1,
[`scripts/bootstrap.sh`](scripts/bootstrap.sh): install git, ansible-core, the required
collections, `python3-dnf`, and `python3-rich`; run `dnf upgrade -y --refresh`; stage
the Stage 2 runner and its systemd unit (`syncopated-bootstrap-root.service`, with
`TimeoutSec=0`); enable the unit and reboot. Stage 2,
[`scripts/syncopated-bootstrap-root.sh`](scripts/syncopated-bootstrap-root.sh): run
`ansible-pull --tags system local.yml`, write `/var/log/syncopated-stage2.done`,
self-disable the unit, and reboot. Stage 3, `syncopated-firstboot` (deployed by the
`common` role to `/usr/local/bin`): hook first login, clone the dotfiles via yadm, and
write the sentinel `~/.local/state/syncopated/firstboot.done`.

There are three convergence paths — the staged bootstrap above; the autonomous yadm
bootstrap, whose `01-ansible-pull.sh` bridges back into Layer 1 with
`SYNCOPATED_ANSIBLE_PULL=yes` for unattended runs; and standalone local convergence —
and all three end at the same place: a converged Layer 1 and a yadm-ready Layer 2.
[`docs/bootstrap.md`](docs/bootstrap.md) is the full lifecycle.

## The rules, and where they came from

The hard rules — the two variable tiers and the fail-fast assert pattern (every role
ships `tasks/assert.yml`) — live in [`AGENTS.md`](AGENTS.md), which is authoritative.
Never auto-commit is standing policy too, recorded as
[failure point 5](docs/failure-points.md#5-never-auto-commit). Variables
come in two tiers: Tier 1 names are semantic and unprefixed (`user.*`, machine hardware,
system-wide capabilities) in `group_vars/` and `host_vars/`; Tier 2 names — role
`defaults/`, `vars/`, and anything created with `register:` — are role-prefixed
(`<role>_*`) to avoid cross-role leakage. Precedence is
`defaults < group_vars < host_vars < extra vars`, covered in depth in
[`docs/variable-precedence.md`](docs/variable-precedence.md).

None of it is decorative: [`docs/conventions.md`](docs/conventions.md) maps each rule to
the documented failure point that produced it, and the conventions are the scar tissue
those 22 failures left behind.

## The build that watches itself

When enabled, the repo-local `llm_analyzer` callback sends each play and task to an LLM
provider — Mistral by default — on a background worker pool and records each prediction
to an append-only trace store. It is opt-in: it requires an API key, self-disables
without one, and when it is on, traces leave the host. [`ansible.cfg`](ansible.cfg)
carries the runtime wiring: jsonfile fact caching (`/tmp/ansible_cache`) and pipelining
are enabled, the `callbacks_enabled` lines are commented out, the active stdout callback
is `rich_ci_formatter`, and a `[callback_llm_analyzer]` section exists with
`provider=mistral`, `model=mistral-medium-latest`, `temperature=0.4`. Then the loop
closes: [`scripts/llm_trainset.py`](scripts/llm_trainset.py) builds a scored DSPy trainset
from the captured traces, and the remediation pipeline lives in the companion
[`llmops`](https://gitlab.com/syncopatedX/llmops) repository. Observe, learn, remediate.

The internals, if you want them:
[`plugins/callback/README.md`](plugins/callback/README.md) covers the callback plugins;
[`plugins/callback_utils/README.md`](plugins/callback_utils/README.md) covers the
support modules and the plugin-namespace trap they exist to avoid; and the
[`docs/llm_analyzer/`](docs/llm_analyzer/README.md) knowledgebase holds an event-ordered
walkthrough with file:line citations
([`how-it-works.md`](docs/llm_analyzer/how-it-works.md)), every
`[callback_llm_analyzer]` option — environment variables win
([`tuning.md`](docs/llm_analyzer/tuning.md)) — and use cases labeled Verified /
Supported-by-code / Not-available ([`use-cases.md`](docs/llm_analyzer/use-cases.md)).

## Improvement cycles (PDCA)

PDCA here means plan-do-check-act: a change is designed, executed, measured, and then
either standardized or revised. Current cycles:

| Read | Status |
|------|--------|
| [`docs/pdca/001-llm-analyzer-dspy.md`](docs/pdca/001-llm-analyzer-dspy.md) | llm_analyzer DSPy refactor — PLAN complete, awaiting DO. |
| [`docs/pdca/002-tuning-fail-fast-assertions.md`](docs/pdca/002-tuning-fail-fast-assertions.md) | Tuning fail-fast assertions — CHECK & ACT complete. |
| [`docs/pdca/003-tuning-package-daemon-convergence.md`](docs/pdca/003-tuning-package-daemon-convergence.md) | Tuning package/daemon convergence — CHECK & ACT complete. |
| [`docs/pdca/004-repo-wide-fail-fast-assertions.md`](docs/pdca/004-repo-wide-fail-fast-assertions.md) | Repo-wide fail-fast assertions — CHECK & ACT complete. |

## Working on the repository

The three `devcontainer.json` variants (podman rootless / podman / docker) and what each
`runArgs` entry does are documented in
[`docs/devcontainer-configuration.md`](docs/devcontainer-configuration.md). `ansible-lint`
runs from the repo root, per [`AGENTS.md`](AGENTS.md).

## The Map

Everything above is the manual; everything below is the map, for the agent reader and the
returning human. Where a row summarizes a target, the target remains authoritative —
treat rows as previews, not replacements. Not covered here:
[`docs/audits/`](docs/audits/) and [`docs/graphs/`](docs/graphs/) (currently empty), and
[`docs/ansible_rich_callback_kb.html`](docs/ansible_rich_callback_kb.html) (an HTML
export, not maintained markdown).

### Role Reference

| Read | It answers |
|------|------------|
| [`roles/common/README.md`](roles/common/README.md) | System baseline, hardware auto-detect, CIS L2 hardening. |
| [`roles/tuning/README.md`](roles/tuning/README.md) | Realtime audio, ZRAM, udev, systemd drop-ins. |
| [`roles/networking/README.md`](roles/networking/README.md) | Interfaces, DNS, profiles. |
| [`roles/containerd/README.md`](roles/containerd/README.md) | Container runtime and dev environment. |
| [`roles/libvirt/README.md`](roles/libvirt/README.md) | KVM/QEMU, daemon security, bridges, pools. |
| [`roles/desktop_ui/README.md`](roles/desktop_ui/README.md) | GNOME/COSMIC/Sway dispatch, extensions, display manager, Yaru. |
| [`roles/tools/README.md`](roles/tools/README.md) | Utilities, IDEs, AI agent CLIs, input-remapper. |
| [`roles/user/README.md`](roles/user/README.md) | uv-managed Python; deliberately small. |
| [`roles/nas/README.md`](roles/nas/README.md) | NFSv4, Samba, Rsync, firewalld, multi-tenant. |
| [`roles/tts/README.md`](roles/tts/README.md) | Whisper — its README is currently an unedited boilerplate stub; [`playbooks/tts.yml`](playbooks/tts.yml) is the better entry point until that is written. |

Role variable references live in each role's `defaults/` and README — standard role
structure per [`AGENTS.md`](AGENTS.md) — not here.

### Companion Repositories

| Repository | Purpose |
|-----------|---------|
| [`osbuild`](https://gitlab.com/syncopatedX/osbuild) | Image building: declarative blueprints (GNOME/COSMIC), ISO/appliance/disk composition, realtime build progress TUI (`bin/osbuild-progress`) |
| [`rpmbuild`](https://gitlab.com/syncopatedX/rpmbuild) | RPM packaging: `rpm_dev` role, mock build chroots |
| [`llmops`](https://gitlab.com/syncopatedX/llmops) | LLM operations: Dify, Langfuse, Hermes, Ollama, remediation pipeline |

## License

MIT — see [`LICENSE`](LICENSE). The badge above carries the same claim.
(Earlier READMEs claimed GPL-3.0-or-later, but no `LICENSE` file was ever
present in the working tree or in git history; that claim is retired in favor
of the MIT file now at the repository root.)

Two files are carved out of the MIT grant and remain GPL with their upstream
credits intact:

- [`plugins/callback/llm_analyzer.py`](plugins/callback/llm_analyzer.py) —
  GPL-3.0-or-later, `Copyright (c) 2023 Sagi Shnaidman` (derived from his
  callback plugin)
- [`roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2`](roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2) —
  GPL-2.0-or-later, `Copyright (C) 2012-2020 Sébastien Luttringer`,
  `Copyright (C) 2024-2025 Francesco Poli` (derived from the Arch Linux
  cpupower unit)

The `vendor/` submodules are separate works governed by their own licenses:
`almalinux-atomic-workstation` (GPL-3.0), `finpilot` (Apache-2.0), and
`osbuild` / `rpmbuild` (MIT, this stack).
