<div align="center">

# Syncopated Workstation

An Ansible control repository for provisioning Fedora, AlmaLinux, and Rocky Linux
workstations — built and maintained with AI coding tools, and provisioning those
same tools onto every managed host.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15%20(verified%202.18--2.20)-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![python](https://img.shields.io/badge/python-3.14%20%7C%203.12%2B-blue.svg)](https://www.python.org/)
[![ruby](https://img.shields.io/badge/ruby-4.0.4-CC342D)](https://www.ruby-lang.org/)

[![Claude Code](https://img.shields.io/badge/Claude_Code-provisioned-D97757)](https://claude.ai/code)
[![Antigravity](https://img.shields.io/badge/Antigravity-provisioned-4285F4)](https://antigravity.google)
[![Crush](https://img.shields.io/badge/Crush-provisioned-E85D75)](https://github.com/charmbracelet/crush)
[![OpenCode](https://img.shields.io/badge/OpenCode-provisioned-1a1a1a)](https://opencode.ai)
[![Mistral Vibe](https://img.shields.io/badge/Mistral_Vibe-provisioned-FF7000)](https://mistral.ai)

[![Fedora](https://img.shields.io/badge/Fedora-44-294172)](https://getfedora.org)
[![AlmaLinux](https://img.shields.io/badge/AlmaLinux-10-099CDB)](https://almalinux.org)
[![Rocky Linux](https://img.shields.io/badge/Rocky_Linux-10-10B981)](https://rockylinux.org)

</div>

---

## What This Is

Ten Ansible roles that provision a workstation — system packages, hardware
acceleration, desktop environment, developer tools, and the AI coding agent CLIs
developers actually use. Idempotent by contract: re-running against a converged
host reports zero changes.

The repository was built by AI coding agents across 512 sessions over nine months.
The failure points those agents hit — and the patterns they developed — are the
actual content of this project. See [`docs/build-process.md`](docs/build-process.md)
for the build history and [`docs/failure-points.md`](docs/failure-points.md) for
the 22 learnings.

## Quick Start

```bash
# Prerequisites: ansible-core >= 2.15, Python 3.12+, root, x86_64,
# Fedora 44 / AlmaLinux 10 / Rocky Linux 10

# Pre-flight check (no mutations)
ansible-playbook playbooks/workstation.yml --tags "assert" --check

# Full provisioning
ansible-playbook playbooks/workstation.yml

# Specific role only
ansible-playbook playbooks/workstation.yml --tags "tools"
```

Full usage instructions: [`docs/usage.md`](docs/usage.md)

---

## For Coding Agents

If you are an AI coding agent starting work in this repository, read this
section first. It is the onboarding overview — everything you need to orient
before touching code.

**What this repository is**: An Ansible control repository for provisioning
Fedora, AlmaLinux, and Rocky Linux workstations. Roles live in `roles/`, playbooks
in `playbooks/`, and `local.yml` at the root is the `ansible-pull` entry point.

**Where things live**:

| Path | Contents |
|------|----------|
| `AGENTS.md` | Project conventions, commands, testing, variable scoping — read this before editing |
| `roles/` | Ten roles: `common`, `tuning`, `networking`, `containerd`, `libvirt`, `desktop_ui`, `tools`, `user`, `nas`, `tts` |
| `playbooks/` | `workstation.yml` (full provisioning), `repositories.yml`, `nas.yml`, `tts.yml` |
| `inventory/` | `hosts.yml`, `group_vars/`, `host_vars/` |
| `docs/` | Architecture, conventions, usage, build process, failure points |
| `plugins/callback/` | `llm_analyzer.py` (opt-in LLM trace), `rich_ci_formatter.py` (terminal output) |
| `scripts/` | Bootstrap stages, ansible-pull bridge, DSPy trainset builder |

**Hard rules** (full details in `AGENTS.md`):

1. **Never auto-commit.** Show the diff, offer the commit, wait for explicit request.
2. **Variable scoping**: Tier 1 (host/domain) variables are unprefixed in `group_vars/`/`host_vars/`. Tier 2 (role-scoped) variables in `defaults/`, `vars/`, and `set_fact` must be role-prefixed (`<role>_*`). Registered variables have global host scope.
3. **Every role has `tasks/assert.yml`** — fail-fast pre-flight validation. Gated by `<role>_assert_enabled | default(true) | bool`. Run with `--tags assert`.
4. **One file, one owner.** Before templating a shared config path, grep for other writers.
5. **Idempotency**: every skip-if-present guard ships with a matching `*_force_install` override variable.
6. **Atomic commits**: one logical change per commit. Classify by intent (`feat`, `fix`, `refactor`, `chore`, `revert`, `docs`).
7. **Layer boundary**: Ansible (Layer 1) never writes into `$HOME` paths that yadm (Layer 2) owns.

**Commands**:

```bash
ansible-playbook playbooks/workstation.yml              # full provisioning
ansible-playbook playbooks/workstation.yml --tags assert --check  # pre-flight only
ansible-lint                                            # lint
molecule test                                           # common role tests
pre-commit run --all-files                              # all hooks
```

**Where to learn more**:

- [`docs/overview.md`](docs/overview.md) — what the project is, structure, layering, tools
- [`docs/conventions.md`](docs/conventions.md) — the rules, with failure-point traceability
- [`docs/failure-points.md`](docs/failure-points.md) — 22 real failures and the patterns they taught
- [`docs/build-process.md`](docs/build-process.md) — the build history from session logs
- [`docs/usage.md`](docs/usage.md) — prerequisites, provisioning, bootstrap, testing
- [`docs/layering-architecture.md`](docs/layering-architecture.md) — Layer 0/1/2 taxonomy
- [`docs/variable-precedence.md`](docs/variable-precedence.md) — variable scoping rules
- [`docs/bootstrap.md`](docs/bootstrap.md) — staged bootstrap lifecycle

---

## Syncopated Agent Workflow (Mistral Vibe)

This repository ships a **6-phase agent workflow** built for Mistral Vibe — a pipeline that takes a request from design through implementation, refactoring, hardening, verification, and architectural review, with a gate at each phase that must pass before work proceeds. I find it a genuine comfort, because it means no change reaches you without having been designed, written, cleaned, hardened, tested, and audited by a specialist who does only that one thing.

### The Pipeline

```
Phase 1: SPECIFIER    →  Design roles, playbooks, variables, acceptance criteria
Phase 2: IMPLEMENTER  →  Write tasks, templates, defaults, handlers
Phase 3: CLEANER      →  Refactor to the 15 Ansible design patterns
Phase 4: HARDENER     →  Add pre-flight assertions, enforce idempotency, security scan
Phase 5: QA           →  ansible-lint, molecule, --check, pre-commit
Phase 6: ARCHITECT    →  Pattern compliance audit, blast-radius assessment
```

Each phase is a **subagent** with its own system prompt, tool permissions, and gate. The **lead agent** orchestrates: it reads your request, decides which phase to start in, delegates via the `task` tool, reviews the output against the phase gate, and either advances or sends the work back with specific feedback.

### The Agents

| Agent | Phase | What it does | Safety |
|-------|-------|-------------|--------|
| `syncopated-lead` | Orchestrator | Reads requests, delegates to phase agents, reconciles results, offers commits | destructive |
| `syncopated-lead-specifier` | 1 — Design | Translates requirements into designs, variable schemas, Gherkin acceptance criteria | neutral |
| `syncopated-lead-implementer` | 2 — Write | Writes production Ansible code following all 15 patterns | destructive |
| `syncopated-lead-cleaner` | 3 — Refactor | Eliminates duplication, enforces pattern compliance | destructive |
| `syncopated-lead-hardener` | 4 — Harden | Adds `tasks/assert.yml`, verifies idempotency, checks layer boundaries | destructive |
| `syncopated-lead-qa` | 5 — Verify | Runs the full verification suite (lint, molecule, check mode, pre-commit) | neutral |
| `syncopated-lead-architect` | 6 — Audit | Audits against 15 patterns, assesses blast radius, updates goal tracking | neutral |

The lead agent (`agent_type = "agent"`) is user-selectable via `--agent syncopated-lead`; the six phase agents (`agent_type = "subagent"`) are spawned by the lead via the `task` tool. Configs live in `.vibe/agents/`, system prompts in `.vibe/prompts/`.

### The Skill

The [`syncopated`](.agents/skills/syncopated/SKILL.md) skill is the operational backbone — it covers project orientation, hard rules, the 6-phase pipeline, variable scoping, the 15 patterns, the verification checklist, and goal tracking. The lead agent loads it automatically (along with [`ansible-patterns-anti-patterns`](.agents/skills/ansible-patterns-anti-patterns/SKILL.md)) via its `enabled_skills` config.

### Using It

Start Mistral Vibe in the repository root with the lead agent selected:

```bash
vibe --agent syncopated-lead
```

Then describe what you want — the lead agent handles the rest:

```
"Add a new role for managing Tailscale VPN on all workstations"
```

The lead agent delegates through the phases in order, stopping at each gate for your review. You can also jump straight to a specific phase if you already know where the work sits:

```
"Run the hardener phase on the tools role — it needs assertions"
"QA the networking role changes I just made"
```

### What Lives Where

| Path | Contents |
|------|----------|
| `.vibe/agents/syncopated-lead.toml` | Lead agent config (orchestrator, user-selectable) |
| `.vibe/agents/syncopated-lead-{specifier,implementer,cleaner,hardener,qa,architect}.toml` | Phase subagent configs |
| `.vibe/prompts/syncopated-lead.md` | Lead agent system prompt (full pipeline, delegation, git rules) |
| `.vibe/prompts/syncopated-lead-{phase}.md` | Phase-specific system prompts |
| `.agents/skills/syncopated/SKILL.md` | Project management skill (conventions, pipeline, checklist) |

---

## Documentation

| Document | What it covers |
|----------|---------------|
| [`docs/overview.md`](docs/overview.md) | Project overview: structure, layering model, coding tools, observability, companion repositories |
| [`docs/build-process.md`](docs/build-process.md) | Build process deconstructed: project lineage, session rhythm, tool distribution, satisfaction |
| [`docs/failure-points.md`](docs/failure-points.md) | 22 failure points from the build, each with what happened, the learning, and the pattern |
| [`docs/usage.md`](docs/usage.md) | Prerequisites, provisioning, pull-based convergence, bootstrap, testing, Vagrant |
| [`docs/conventions.md`](docs/conventions.md) | Variable scoping, pre-flight assertions, firewall, atomic commits, ownership, idempotency |
| [`docs/layering-architecture.md`](docs/layering-architecture.md) | Layer 0/1/2 taxonomy (OSBuild / Ansible / yadm) |
| [`docs/variable-precedence.md`](docs/variable-precedence.md) | Variable precedence chain and naming conventions |
| [`docs/bootstrap.md`](docs/bootstrap.md) | Staged bootstrap lifecycle details |
| [`docs/audit-notes.md`](docs/audit-notes.md) | Terminology, uncertainty labels, evidence sourcing |

## Companion Repositories

| Repository | Purpose |
|-----------|---------|
| [`osbuild`](https://gitlab.com/syncopatedX/osbuild) | Image building: declarative blueprints, ISO/appliance/disk composition |
| [`rpmbuild`](https://gitlab.com/syncopatedX/rpmbuild) | RPM packaging: `rpm_dev` role, mock build chroots |
| [`llmops`](https://gitlab.com/syncopatedX/llmops) | LLM operations: Dify, Langfuse, Hermes, Ollama, remediation pipeline |

---

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) for the full text.
