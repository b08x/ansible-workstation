# Project Overview

This document describes what the Syncopated workstation repository is, what lives
inside it, and how the pieces fit together. For the build history and the failure
points that shaped it, see [`build-process.md`](build-process.md) and
[`failure-points.md`](failure-points.md). For day-to-day usage,
see [`usage.md`](usage.md).

---

## What This Is

This repository provisions workstations. It installs system packages, configures
services, detects hardware acceleration (CUDA, Vulkan, Intel
oneAPI/SYCL) and installs those vendor stacks through the optional `gpu`
role, deploys desktop environments, and — centrally — installs the AI
coding agent CLIs this workstation runs day to day: Claude Code, Google
Antigravity, Charm Crush, and OpenCode.

But that is the *output*. The more interesting story is the *input*: this
repository was built by AI coding agents, working in sessions that left a
trace — and that trace is now part of the project. Across the full lineage of
this repository (tracked under 46 project entries in the code-insights corpus,
from `ansible-rhel-workstation-builder` through `ansible-collection-rhel-workstation-builder`
through `syncopated-ansible` through `Archive/Ansible` through `ansible` to the
current `workstation`), 512 sessions over roughly nine months (January–October
2026) produced it, at an estimated token cost of $2,057. The detailed corpus
counts — messages, learnings, architectural decisions, facet analyses,
prompt-quality assessments — live in [`build-process.md`](build-process.md),
their canonical home.

The functional use-case is straightforward: **manage an Ansible project with
coding tools**. Across the corpus, AI coding agents wrote, debugged, refactored,
and committed the roles, playbooks, and plugins in this repository — though the
corpus may not capture every manual edit. The failure points
those agents hit — and the patterns they developed to avoid repeating them —
are documented in [`failure-points.md`](failure-points.md), because they are the
actual content of this project. The Ansible roles are the artifact; the
learnings are the payload.

---

## Repository Structure

```
workstation/
├── local.yml                  # ansible-pull playbook for local convergence
├── ansible.cfg                # Fact caching, pipelining, callback plugins
├── ansible-navigator.yml      # Navigator configuration
├── playbooks/
│   ├── workstation.yml        # Full multi-host provisioning
│   ├── repositories.yml       # DNF repository configuration
│   ├── nas.yml                # NAS playbook
│   └── tts.yml                # Text-to-speech playbook
├── roles/
│   ├── common/                # Base system, firstboot, hardening, Molecule tests
│   ├── tuning/                # Kernel params, zram, CPU tuning
│   ├── networking/            # Network configuration
│   ├── containerd/            # Container runtime
│   ├── libvirt/               # Virtualization (KVM)
│   ├── desktop_ui/            # GNOME & COSMIC desktop, GDM & cosmic-greeter, theming
│   ├── gpu/                   # Optional Intel oneAPI + NVIDIA CUDA stacks (off by default)
│   ├── tools/                 # AI coding CLIs, IDEs, system binaries, Flatpaks
│   ├── user/                  # User environment, shell, uv toolchains
│   ├── nas/                   # NFS, Samba, rsync
│   └── tts/                   # Text-to-speech services
├── inventory/
│   ├── hosts.yml              # Host inventory
│   ├── group_vars/            # Group variables
│   └── host_vars/             # Per-host variables
├── plugins/
│   └── callback/
│       ├── llm_analyzer.py    # Records every play/task to a trace store
│       └── rich_ci_formatter.py # Human-readable terminal output
├── scripts/
│   ├── bootstrap.sh           # Stage 1: minimal prerequisites + reboot
│   ├── syncopated-bootstrap-root.sh  # Stage 2: systemd runner for ansible-pull
│   ├── syncopated-firstboot   # Stage 3: user login bootstrap
│   ├── 01-ansible-pull.sh     # Yadm bridge to ansible-pull
│   └── llm_trainset.py        # Builds DSPy trainset from traces
├── docs/
│   ├── layering-architecture.md  # Layer 0/1/2 taxonomy
│   ├── bootstrap.md              # Bootstrap lifecycle details
│   └── variable-precedence.md    # Variable scoping rules
└── Vagrantfile                # libvirt Fedora VM for testing
```

---

## The Layering Model

Three layers, strictly owned (see [`layering-architecture.md`](layering-architecture.md)
for the full taxonomy):

- **Layer 0 — OSBuild** (the floor): Immutable base images. Kernel, drivers,
  container runtimes, core packages. Built, never mutated. Lives in the
  companion `osbuild` repository.
- **Layer 1 — Ansible** (the system): Host-level packages, services, hardware
  acceleration, developer IDEs, coding agent CLIs, system Flatpaks. Idempotent
  by contract — re-running against a converged host reports zero changes.
- **Layer 2 — yadm** (the user): Dotfiles, shell environment, user version
  managers, user Cargo crates, user Ruby gems, user Flatpaks. The one layer a
  re-image does not erase; drift is permitted under version control.

Layer 2 is not passive: before user configuration is applied, yadm's first
bootstrap step, `scripts/01-ansible-pull.sh`, bridges back down into Ansible
(`ansible-pull --tags user local.yml`), so the top of the stack can pull its own
floor into shape — see [`bootstrap.md`](bootstrap.md) for the bridge and
[`layering-architecture.md`](layering-architecture.md) for the boundary it crosses.

---

## The Coding Tools

The standalone playbooks in [`playbooks/agent-harness/`](../playbooks/agent-harness/) provision four AI coding agent CLIs:

| CLI | Binary | Install Method | Config Location |
|-----|--------|---------------|-----------------|
| Claude Code | `claude` | npm global (user prefix) | `~/.claude/settings.json` |
| Google Antigravity | `agy` | Direct binary download | `~/.config/antigravity/` |
| Charm Crush | `crush` | Go compile (`~/go/bin`) | `~/.config/crush/` |
| OpenCode | `opencode` | npm global (user prefix) | `~/.config/opencode/` |

Ansible installs the binaries; yadm (Layer 2) owns the configs and shared
skills. The boundary is strict — Ansible never writes into paths that
yadm owns.

Plus developer IDEs (VS Code — a real opt-in), system Flatpaks, and the
input-remapper service — all in the tools role and gated by explicit boolean
flags (`tools_install_*`). User-space toolchains and extension lists migrated
to the user role: bun (`~/.bun/bin/bun`), the Go toolchain
(system-first with a user tarball fallback), cargo crates, GNOME Shell
extensions, and VS Code extensions, all gated by `user_install_*` flags.
transcribe.cpp (Whisper CLI, compiled
from source with a CUDA, Intel SYCL, or Vulkan backend chosen by hardware
probe; GPU required by default) is built by the standalone opt-in
[`playbooks/transcribe-cpp.yml`](../playbooks/transcribe-cpp.yml) playbook, configured
via its `transcribe_*` extra vars.

---

## Observability: the loop

When the `llm_analyzer` callback is enabled via `callbacks_enabled` (opt-in,
disabled by default) and an API key exists, every play and task this repository
runs is sent to a configurable LLM provider — Mistral by default in
`ansible.cfg` — on a background worker pool, with predictions recorded to an
append-only trace store and markdown under `llm_analysis/`. Without a key the
callback disables itself and the run goes unobserved; when it is on, play and
task content leaves the host — treat traces as sensitive. The accumulated
traces then become a scored DSPy trainset via `scripts/llm_trainset.py`, and
the companion `llmops` repository runs a diagnose-and-fix remediation pipeline
with mechanical safety guards against the learnings. The build's own execution
history becomes training material for improving the build: observe (trace +
render), learn (trainset), remediate (llmops).

For the human at the terminal, `rich_ci_formatter` renders the same runs:
DNF5 transaction tables, systemd transitions, phase banners.

---

## Companion Repositories

| Repository | Purpose |
|-----------|---------|
| [`osbuild`](https://gitlab.com/syncopatedX/osbuild) | Image building: declarative blueprints (GNOME/COSMIC), ISO/appliance/disk composition, package taxonomy, realtime progress TUI (`bin/osbuild-progress`) |
| [`rpmbuild`](https://gitlab.com/syncopatedX/rpmbuild) | RPM packaging: `rpm_dev` role, mock build chroots, packaging environments |
| [`llmops`](https://gitlab.com/syncopatedX/llmops) | LLM operations: Dify, Langfuse, Hermes, Ollama, remediation pipeline |
