<div align="center">

# Syncopated Workstation

An Ansible control repository provisioning Fedora 44 / AlmaLinux 10 / Rocky Linux 10
workstations. Ten roles. ansible-core >= 2.15, Python 3.12+ (3.14 aligned), x86_64, root required.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15%20(verified%202.18--2.20)-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![python](https://img.shields.io/badge/python-3.14%20%7C%203.12%2B-blue.svg)](https://www.python.org/)

</div>

---

This page is an index, not a manual. Its job is to route you — human operator or AI
coding agent — to the document that answers your question; the linked files carry the
detail. The repository was built by AI coding agents across 512 sessions over nine
months, and the failure patterns from those sessions are encoded as this repo's
conventions. I find that provenance worth knowing up front: the conventions below
trace back to documented failure points — [`docs/conventions.md`](docs/conventions.md)
maps each rule to one.

## Start Here

| Read | It answers |
|------|------------|
| [`docs/overview.md`](docs/overview.md) | What is this repo? Structure, layering model, tools. |
| [`AGENTS.md`](AGENTS.md) | Project conventions, commands, testing, variable scoping — read this before editing. |
| [`docs/audit-notes.md`](docs/audit-notes.md) | How does the docs/ corpus source its evidence and label its uncertainty? |

## Getting Started & Operating

| Read | It answers |
|------|------------|
| [`docs/usage.md`](docs/usage.md) | Prerequisites, provisioning, tags, `--check`, bootstrap, testing, Vagrant. |
| [`docs/bootstrap.md`](docs/bootstrap.md) | The staged bootstrap lifecycle and the three convergence paths (convergence = running the playbooks until the host matches its declared state). |
| [`local.yml`](local.yml) | Root-level `ansible-pull` entry point for autonomous local convergence (`ansible-pull -U <repo-url> --tags system local.yml`); run instructions in its header comments and `docs/usage.md`. |
| [`playbooks/workstation.yml`](playbooks/workstation.yml) | Full host provisioning; imports `playbooks/repositories.yml` first; targets the `workstations` group. |
| [`playbooks/repositories.yml`](playbooks/repositories.yml) | DNF configuration, repository setup, package updates. |
| [`playbooks/nas.yml`](playbooks/nas.yml) | NAS services (NFSv4, Samba, Rsync, firewalld); runs against `hosts: all`. |
| [`playbooks/tts.yml`](playbooks/tts.yml) | Whisper TTS; targets `hosts: workstations`. |
| [`ansible.cfg`](ansible.cfg) | Runtime configuration: jsonfile fact caching (`/tmp/ansible_cache`) and pipelining are enabled; all `callbacks_enabled` lines are commented out; the active stdout callback is `rich_ci_formatter`; a `[callback_llm_analyzer]` section exists with `provider=mistral`, `model=mistral-medium-latest`, `temperature=0.4`. |

A pre-flight then full provisioning — full runbook in [`docs/usage.md`](docs/usage.md):

```bash
# Pre-flight: run every role's assertions, mutate nothing
ansible-playbook playbooks/workstation.yml --tags assert --check

# Full provisioning
ansible-playbook playbooks/workstation.yml
```

Everything else — tags, specific roles, Vagrant — is in [`docs/usage.md`](docs/usage.md).

## Architecture

| Read | It answers |
|------|------------|
| [`docs/layering-architecture.md`](docs/layering-architecture.md) | How do the layers divide ownership? Layer 0 OSBuild immutable base, Layer 1 Ansible host, Layer 2 yadm user-space — with strict ownership boundaries. |
| [`docs/end-to-end-validation.md`](docs/end-to-end-validation.md) | What does one request look like from spec sentence to converged host? Per-stage evidence calibration. |

## Conventions & Rules

| Read | It answers |
|------|------------|
| [`docs/conventions.md`](docs/conventions.md) | What are the rules, and which failure points do they trace to? |
| [`docs/variable-precedence.md`](docs/variable-precedence.md) | Variable scoping: Tier 1 unprefixed domain, Tier 2 role-prefixed; precedence `defaults < group_vars < host_vars < extra vars`. |
| [`AGENTS.md`](AGENTS.md) | The authoritative hard-rules list. |

The hard rules — never auto-commit, the two variable tiers, every role ships
`tasks/assert.yml` — live in [`AGENTS.md`](AGENTS.md), and this index does not
duplicate them.

## Role Reference

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

Role variable references live in each role's `defaults/` and README — standard role structure per [`AGENTS.md`](AGENTS.md) — not here.

## Plugins & Internals

| Read | It answers |
|------|------------|
| [`plugins/callback/README.md`](plugins/callback/README.md) | The repo-local callback plugins: `llm_analyzer.py`, `rich_ci_formatter.py`. |
| [`plugins/callback_utils/README.md`](plugins/callback_utils/README.md) | Support modules — and the plugin-namespace trap, documented. |
| [`docs/llm_analyzer/README.md`](docs/llm_analyzer/README.md) | Entry point for the llm_analyzer knowledgebase. |
| [`docs/llm_analyzer/how-it-works.md`](docs/llm_analyzer/how-it-works.md) | Event-ordered walkthrough, with file:line citations. |
| [`docs/llm_analyzer/tuning.md`](docs/llm_analyzer/tuning.md) | Every `[callback_llm_analyzer]` option; environment variables win. |
| [`docs/llm_analyzer/use-cases.md`](docs/llm_analyzer/use-cases.md) | Use cases, labeled Verified / Supported-by-code / Not-available. |
| [`scripts/llm_trainset.py`](scripts/llm_trainset.py) | DSPy trainset builder from captured traces. |

## Development Environment

| Read | It answers |
|------|------------|
| [`docs/devcontainer-configuration.md`](docs/devcontainer-configuration.md) | The three `devcontainer.json` variants (podman rootless / podman / docker) and what each `runArgs` entry does. |

## The 6-Phase Agent Workflow

This repository ships a 6-phase agent workflow — Specifier, Implementer, Cleaner,
Hardener, QA, Architect — with a lead agent (`syncopated-lead`) orchestrating the
handoffs, one subagent per phase. It runs in both Google Antigravity CLI (`agy`) and
Mistral Vibe. Deeper detail lives in the agent definition files linked below and in
[`.vibe/README.md`](.vibe/README.md), not here.

| Read | It answers |
|-------|-------------------|
| [`.agents/agents/syncopated-lead.md`](.agents/agents/syncopated-lead.md) (+ 6 phase variants) | Antigravity agent definitions. |
| [`.vibe/agents/syncopated-lead.toml`](.vibe/agents/syncopated-lead.toml) (+ phase variants) | Vibe agent configs. |
| [`.vibe/prompts/`](.vibe/prompts/) | The 7 Vibe system prompt files. |
| [`.vibe/README.md`](.vibe/README.md) | The Vibe-harness layout doc. |
| [`scripts/validate-agents.sh`](scripts/validate-agents.sh) | Validation suite for the agent definitions. |
| [`scripts/install-agents.sh`](scripts/install-agents.sh) | Installs the agent definitions and symlinks them into `~/.gemini/agents/`. |

```bash
agy --agent syncopated-lead    # Google Antigravity CLI
vibe --agent syncopated-lead  # Mistral Vibe
```

## Skills for Agents

| Read | It answers |
|------|-----------|
| [`.agents/skills/ansible-patterns-anti-patterns/SKILL.md`](.agents/skills/ansible-patterns-anti-patterns/SKILL.md) | The 15 Ansible design patterns. |
| [`.agents/skills/syncopated/SKILL.md`](.agents/skills/syncopated/SKILL.md) | The core project workflow. |
| [`.agents/skills/langfuse/SKILL.md`](.agents/skills/langfuse/SKILL.md) | Langfuse integration. |
| [`.agents/skills/zread/README.md`](.agents/skills/zread/README.md) | The zread CLI skill. |
| [`skills/system/run-workflow/SKILL.md`](skills/system/run-workflow/SKILL.md) | The dynamic workflow runner. |

## Improvement Cycles (PDCA)

PDCA here means plan-do-check-act: a change is designed, executed, measured, and
then either standardized or revised. Current cycles:

| Read | Status |
|------|--------|
| [`docs/pdca/001-llm-analyzer-dspy.md`](docs/pdca/001-llm-analyzer-dspy.md) | llm_analyzer DSPy refactor — PLAN complete, awaiting DO. |
| [`docs/pdca/002-tuning-fail-fast-assertions.md`](docs/pdca/002-tuning-fail-fast-assertions.md) | Tuning fail-fast assertions — CHECK & ACT complete. |
| [`docs/pdca/003-tuning-package-daemon-convergence.md`](docs/pdca/003-tuning-package-daemon-convergence.md) | Tuning package/daemon convergence — CHECK & ACT complete. |
| [`docs/pdca/004-repo-wide-fail-fast-assertions.md`](docs/pdca/004-repo-wide-fail-fast-assertions.md) | Repo-wide fail-fast assertions — CHECK & ACT complete. |

## Learnings & History

| Read | It answers |
|------|------------|
| [`docs/failure-points.md`](docs/failure-points.md) | 22 real build failures, and the pattern each one taught. |
| [`docs/build-process.md`](docs/build-process.md) | The build history — 512 AI sessions over ~9 months. |

## What This Index Does Not Do

This index routes. Where a row summarizes a target, the target remains
authoritative — treat rows as previews, not replacements. Not covered here:
[`docs/audits/`](docs/audits/) and [`docs/graphs/`](docs/graphs/) (currently empty),
and [`docs/ansible_rich_callback_kb.html`](docs/ansible_rich_callback_kb.html) (an
HTML export, not maintained markdown). `ansible-lint` runs from the repo root, per
[`AGENTS.md`](AGENTS.md).

## Companion Repositories

| Repository | Purpose |
|-----------|---------|
| [`osbuild`](https://gitlab.com/syncopatedX/osbuild) | Image building: declarative blueprints (GNOME/COSMIC), ISO/appliance/disk composition, realtime build progress TUI (`bin/osbuild-progress`) |
| [`rpmbuild`](https://gitlab.com/syncopatedX/rpmbuild) | RPM packaging: `rpm_dev` role, mock build chroots |
| [`llmops`](https://gitlab.com/syncopatedX/llmops) | LLM operations: Dify, Langfuse, Hermes, Ollama, remediation pipeline |

## License

The license claim is GPL-3.0-or-later — the badge above and the previous README
both carry it. The `LICENSE` file itself is not present in the working tree or in git
history as of this writing; the previous README linked to one, and that link was
dead. I'd rather state that plainly than point you at a file that isn't there.
Adding the file to the repo would resolve the gap; nothing else is needed.
