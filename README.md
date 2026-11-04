<div align="left">

# Ansible Collection: Development Workstation

An Ansible control repository provisioning Fedora 44 / AlmaLinux 10 / Rocky Linux 10
workstations. Eleven roles. ansible-core >= 2.15, Python 3.12+ (3.14 aligned), x86_64, root required.

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

An Ansible control repository that converges a Fedora 44 / AlmaLinux 10 / Rocky Linux 10
x86_64 host into a workstation. The machine is built in three layers, and each layer
owns exactly one thing: Layer 0 is one of two base-system paths — a working ISO
installer pipeline or an unfinished bootc container-image pipeline — composed in the
companion osbuild repository (see
[The layers, and who owns what](#the-layers-and-who-owns-what)); Layer 1 is this
repository, Ansible orchestration for everything the host itself is; Layer 2 is yadm,
your dotfiles, the one layer a re-image does not erase.
[docs/overview.md](docs/overview.md) is the full structural tour;
[docs/layering-architecture.md](docs/layering-architecture.md) covers the layer model
and its strict ownership boundaries.

Read this page in one of two ways. If you are the human owner, read top to bottom: the
sections run from your first command to a full picture of the machine you are about to
live inside. If you are an AI coding agent, use the contents list below or skim to
[The Map](#the-map) for exact paths, and treat [AGENTS.md](AGENTS.md) as the
authoritative hard-rules list before you edit anything. The corpus states its own
evidence rules openly — how it sources claims and labels its uncertainty is documented
in [docs/audit-notes.md](docs/audit-notes.md).

## Contents

- [The layers, and who owns what](#the-layers-and-who-owns-what)
- [From bare metal to logged in](#from-bare-metal-to-logged-in)
- [Converge a host in two commands](#converge-a-host-in-two-commands)
- [The rules, and where they came from](#the-rules-and-where-they-came-from)
- [The build that watches itself](#the-build-that-watches-itself)
- [Improvement cycles (PDCA)](#improvement-cycles-pdca)
- [Working on the repository](#working-on-the-repository)
- [The Map](#the-map)
- [Where to go from here](#where-to-go-from-here)
- [License](#license)

## The layers, and who owns what

Layer 0 is the floor, and it comes from one of two paths in the companion
[osbuild](https://gitlab.com/syncopatedX/osbuild) repository: the **ISO installer
pipeline** — declarative blueprints, functional as intended with minor fixes still
pending — or the **bootc immutable container-image pipeline**, which is unfinished; do
not rely on it yet. Layer 1 does not care which floor it stands on: either way it
starts from a Fedora 44 / AlmaLinux 10 / Rocky Linux 10 host and converges it. Layer 1
is this repository: Ansible converging the host through eleven roles — common,
containerd, desktop_ui, gpu, libvirt, nas, networking, tools, tts, tuning,
user — idempotent by contract. Layer 2 is yadm: the user's dotfiles, cloned on first
login and owned by the user forever after.

The boundaries are strict by design: single ownership, no template clobbering,
separation of binaries and dotfiles, and fail-fast preconditions — every role ships
tasks/assert.yml, gated by <role>_assert_enabled | default(true) | bool, tagged
[<role>, assert, always], and runnable standalone via --tags assert in under a
second.

The Layer 1 surface is five entry points:

- [local.yml](local.yml) — the root-level ansible-pull entry point for autonomous
  local convergence. Two decoupled plays: system provisioning (become: true,
  --tags system) with pre-flight hardware auto-detection — KVM via /dev/kvm,
  graphical display target, containers, CUDA/Vulkan GPUs — plus fail-fast assertions
  and reboot assessment; and user provisioning (become: false, --tags user) with
  uv-managed Python.

  ```bash
  ansible-pull -U <repo-url> --tags system local.yml
  ansible-pull -U <repo-url> --tags user local.yml
  ```

  Run instructions are in its header comments and [docs/usage.md](docs/usage.md).
- [playbooks/workstation.yml](playbooks/workstation.yml) — full multi-host
  provisioning; imports [playbooks/repositories.yml](playbooks/repositories.yml) (DNF
  configuration, repository setup, package updates) first, then targets the
  workstations group (tinybot, gir).
- [playbooks/nas.yml](playbooks/nas.yml) — NAS services (NFSv4, Samba, Rsync,
  firewalld) against hosts: all.
- [playbooks/tts.yml](playbooks/tts.yml) — Whisper TTS against
  hosts: workstations.

## From bare metal to logged in

The bootstrap is the repository reaching out of git and into the machine: Stage 1
stages Stage 2, Stage 2 pulls this repository onto the host and runs it against
itself, and Stage 3 hands off to Layer 2. Each stage writes its sentinel so the next
stage knows what the machine has already become. (On-disk artifact names containing
"syncopated" are historical and unchanged — they are literal file, service, and
sentinel names, cited exactly as they exist.)

Convergence means running the playbooks until the host matches its declared state. The
staged bootstrap gets a bare machine there in three stages. Stage 1,
[scripts/bootstrap.sh](scripts/bootstrap.sh): install git, ansible-core, the required
collections, python3-dnf, and python3-rich; run dnf upgrade -y --refresh; stage
the Stage 2 runner and its systemd unit (syncopated-bootstrap-root.service, with
TimeoutSec=0); enable the unit and reboot. Stage 2,
[scripts/syncopated-bootstrap-root.sh](scripts/syncopated-bootstrap-root.sh): run
ansible-pull --tags system local.yml, write /var/log/syncopated-stage2.done,
self-disable the unit, and reboot. Stage 3, syncopated-firstboot (deployed by the
common role to /usr/local/bin): hook first login, clone the dotfiles via yadm, and
write the sentinel ~/.local/state/syncopated/firstboot.done.

The pipeline has a deliberate stopping point: the pristine checkpoint. The machine
converges itself and then stops just before the part that is yours — build defaults
are generate-only, and on first login syncopated-firstboot prompts for the dotfiles
repository and validates it with git ls-remote before cloning anything.
[docs/end-to-end-validation.md](docs/end-to-end-validation.md) traces a single request
from spec sentence to converged host, with per-stage evidence calibration.

There are three convergence paths — the staged bootstrap above; the autonomous yadm
bootstrap, whose 01-ansible-pull.sh bridges back into Layer 1 with
SYNCOPATED_ANSIBLE_PULL=yes for unattended runs; and standalone local convergence —
and all three end at the same place: a converged Layer 1 and a yadm-ready Layer 2.
[docs/bootstrap.md](docs/bootstrap.md) is the full lifecycle.

## Converge a host in two commands

For a host that is already bootstrapped (or simply inventoried — see the
prerequisites).

Prerequisites:

- ansible-core >= 2.15 (verified 2.18–2.20)
- Python 3.12+ (3.14 on Fedora 44)
- x86_64
- root for the system layer
- Fedora 44, AlmaLinux 10, or Rocky Linux 10
- An inventory entry for your host in [inventory/hosts.yml](inventory/hosts.yml) —
  [playbooks/workstation.yml](playbooks/workstation.yml) targets the workstations
  group (tinybot, gir), so a host outside that group matches nothing

```bash
# Pre-flight: run every role's assertions, mutate nothing
ansible-playbook playbooks/workstation.yml --tags assert --check

# Full provisioning
ansible-playbook playbooks/workstation.yml
```

The pre-flight runs every role's tasks/assert.yml — platform, package manager, init
manager, effective root, identity variables — and mutates nothing; a failed assertion
stops the run in under a second. Illustrative sample output, not captured from a real
run:

```text
TASK [common : assert | platform, package manager, and effective root] ****
fatal: [tinybot]: FAILED! => {"changed": false, "msg": "Assertion failed: effective user is not root (id -u != 0)"}
```

The full run is idempotent by contract. Convergence is the fixed point: run the
playbook again and it reports zero changes — the run is a function, and the converged
host is where it stops moving. Fail fast, mutate never: assertions check before
anything changes. Illustrative sample output of a converged re-run:

```text
PLAY RECAP ********************************************************************
tinybot : ok=214 changed=0 unreachable=0 failed=0
```

Tags, single-role runs, --check, Vagrant, and testing are in
[docs/usage.md](docs/usage.md).

## The rules, and where they came from

The repository was built by AI coding agents across 512 sessions over nine months,
and the failure patterns from those sessions are encoded as this repo's conventions —
which now govern the agents that extend it. [docs/build-process.md](docs/build-process.md)
is that history; [docs/failure-points.md](docs/failure-points.md) records the 22 real
build failures and the pattern each one taught.

The hard rules — the two variable tiers and the fail-fast assert pattern (every role
ships tasks/assert.yml) — live in [AGENTS.md](AGENTS.md), which is authoritative.
Never auto-commit is standing policy too, recorded as
[failure point 5](docs/failure-points.md#5-never-auto-commit). Variables
come in two tiers: Tier 1 names are semantic and unprefixed (user.*, machine hardware,
system-wide capabilities) in group_vars/ and host_vars/; Tier 2 names — role
defaults/, vars/, and anything created with register: — are role-prefixed
(<role>_*) to avoid cross-role leakage. Precedence is
defaults < group_vars < host_vars < extra vars, covered in depth in
[docs/variable-precedence.md](docs/variable-precedence.md).

None of it is decorative: [docs/conventions.md](docs/conventions.md) maps each rule to
the documented failure point that produced it, and the conventions are the scar tissue
those 22 failures left behind.

## The build that watches itself

When enabled, the repo-local llm_analyzer callback sends each play and task to an LLM
provider — Mistral by default — on a background worker pool and records each
prediction to an append-only trace store. It is opt-in: it requires an API key,
self-disables without one, and when it is on, traces leave the host. The relevant
[ansible.cfg](ansible.cfg) wiring, exactly as it exists on disk — note the
callbacks_enabled lines are commented out, so the analyzer and profile_tasks are both
opt-in:

```ini
stdout_callback         = rich_ci_formatter
#callbacks_enabled       = profile_tasks,llm_analyzer
#callbacks_enabled       = profile_tasks
#callbacks_enabled       = llm_analyzer

fact_caching            = jsonfile
fact_caching_connection = /tmp/ansible_cache
fact_caching_prefix     = ansible_facts_
fact_caching_timeout    = 86400

[ssh_connection]
pipelining              = True

[callback_llm_analyzer]
provider = mistral
# Overridden by the AI_MODEL environment variable when it is set.
model = mistral-medium-latest
```

The [callback_llm_analyzer] section also sets temperature = 0.4. From there, the
traces feed forward: [scripts/llm_trainset.py](scripts/llm_trainset.py) builds a
scored DSPy trainset from the captured traces, and the remediation pipeline lives in
the companion [llmops](https://gitlab.com/syncopatedX/llmops) repository. Observe,
learn, remediate.

The internals, if you want them:
[plugins/callback/README.md](plugins/callback/README.md) covers the callback plugins;
[plugins/callback_utils/README.md](plugins/callback_utils/README.md) covers the
support modules and the plugin-namespace trap they exist to avoid; and the
[docs/llm_analyzer/](docs/llm_analyzer/README.md) knowledgebase holds an event-ordered
walkthrough with file:line citations
([how-it-works.md](docs/llm_analyzer/how-it-works.md)), every
[callback_llm_analyzer] option — environment variables win
([tuning.md](docs/llm_analyzer/tuning.md)) — and use cases labeled Verified /
Supported-by-code / Not-available ([use-cases.md](docs/llm_analyzer/use-cases.md)).

## Improvement cycles (PDCA)

PDCA here means plan-do-check-act: a change is designed, executed, measured, and then
either standardized or revised. Current cycles:

| Cycle | What it is | Status |
|-------|------------|--------|
| [001-llm-analyzer-dspy](docs/pdca/001-llm-analyzer-dspy.md) | llm_analyzer DSPy refactor | PLAN complete, awaiting DO |
| [002-tuning-fail-fast-assertions](docs/pdca/002-tuning-fail-fast-assertions.md) | Tuning fail-fast assertions | CHECK & ACT complete |
| [003-tuning-package-daemon-convergence](docs/pdca/003-tuning-package-daemon-convergence.md) | Tuning package/daemon convergence | CHECK & ACT complete |
| [004-repo-wide-fail-fast-assertions](docs/pdca/004-repo-wide-fail-fast-assertions.md) | Repo-wide fail-fast assertions | CHECK & ACT complete |

## Working on the repository

The three devcontainer.json variants (podman rootless / podman / docker) and what each
runArgs entry does are documented in
[docs/devcontainer-configuration.md](docs/devcontainer-configuration.md). ansible-lint
runs from the repo root, per [AGENTS.md](AGENTS.md).

## The Map

Rows summarize; linked targets are authoritative. Not covered here:
[docs/audits/](docs/audits/) and [docs/graphs/](docs/graphs/) (currently empty), and
[docs/ansible_rich_callback_kb.html](docs/ansible_rich_callback_kb.html) (an HTML
export, not maintained markdown).

### Role Reference

| Read | It answers |
|------|------------|
| [roles/common/README.md](roles/common/README.md) | System baseline, hardware auto-detect, CIS L2 hardening. |
| [roles/tuning/README.md](roles/tuning/README.md) | Realtime audio, ZRAM, udev, systemd drop-ins. |
| [roles/networking/README.md](roles/networking/README.md) | Interfaces, DNS, profiles. |
| [roles/containerd/README.md](roles/containerd/README.md) | Container runtime and dev environment. |
| [roles/libvirt/README.md](roles/libvirt/README.md) | KVM/QEMU, daemon security, bridges, pools. |
| [roles/desktop_ui/README.md](roles/desktop_ui/README.md) | GNOME/COSMIC/Sway dispatch, extensions, display manager, Yaru. |
| [roles/gpu/README.md](roles/gpu/README.md) | Optional Intel oneAPI/graphics and NVIDIA CUDA stacks, off by default per host. |
| [roles/tools/README.md](roles/tools/README.md) | Utilities, IDEs, AI agent CLIs, input-remapper. |
| [roles/user/README.md](roles/user/README.md) | uv-managed Python; deliberately small. |
| [roles/nas/README.md](roles/nas/README.md) | NFSv4, Samba, Rsync, firewalld, multi-tenant. |
| [roles/tts/README.md](roles/tts/README.md) | Whisper — its README is currently an unedited boilerplate stub; [playbooks/tts.yml](playbooks/tts.yml) is the better entry point until that is written. |

Role variable references live in each role's defaults/ and README — standard role
structure per [AGENTS.md](AGENTS.md) — not here.

### Companion Repositories

| Repository | Purpose |
|-----------|---------|
| [osbuild](https://gitlab.com/syncopatedX/osbuild) | Image building: declarative blueprints (GNOME/COSMIC), ISO/appliance/disk composition, realtime build progress TUI (bin/osbuild-progress). The ISO installer pipeline works as intended (minor fixes pending); the bootc image pipeline is unfinished. |
| [rpmbuild](https://gitlab.com/syncopatedX/rpmbuild) | RPM packaging: rpm_dev role, mock build chroots |
| [llmops](https://gitlab.com/syncopatedX/llmops) | LLM operations: Dify, Langfuse, Hermes, Ollama, remediation pipeline |

## Where to go from here

If you are the owner, continue with [docs/bootstrap.md](docs/bootstrap.md) for the
full machine lifecycle or [docs/usage.md](docs/usage.md) for day-to-day operations.
If you are an AI coding agent, read [AGENTS.md](AGENTS.md) end to end, then work from
[The Map](#the-map).

## License

MIT — see [LICENSE](LICENSE). (Earlier READMEs claimed GPL-3.0-or-later, but no
LICENSE file was ever present in the working tree or in git history; that claim is
retired in favor of the MIT file now at the repository root.)

Two files are carved out of the MIT grant and remain GPL with their upstream
credits intact:

- [plugins/callback/llm_analyzer.py](plugins/callback/llm_analyzer.py) —
  GPL-3.0-or-later, Copyright (c) 2023 Sagi Shnaidman (derived from his
  callback plugin)
- [roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2](roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2) —
  GPL-2.0-or-later, Copyright (C) 2012-2020 Sébastien Luttringer,
  Copyright (C) 2024-2025 Francesco Poli (derived from the Arch Linux
  cpupower unit)

The vendor/ submodules are separate works governed by their own licenses:
almalinux-atomic-workstation (GPL-3.0), finpilot (Apache-2.0), and
osbuild / rpmbuild (MIT, this stack).
