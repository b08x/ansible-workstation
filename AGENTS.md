<!--# cspell: ignore SSOT CMDB -->
# AGENTS.md

Ensure that all practices and instructions described by
<https://raw.githubusercontent.com/ansible/ansible-creator/refs/heads/main/docs/agents.md>
are followed.

## Project Structure

All Ansible roles are located directly in `roles/`. The project has been consolidated into a single monolithic repository.

All multi-host orchestration playbooks live in `playbooks/`, with `local.yml` at the repository root for pull-based local provisioning:

- `local.yml` — autonomous local workstation pull and convergence playbook for `ansible-pull` and local bootstrap. Lives at the repository root by `ansible-pull` default discovery convention. Implements the 15 Ansible Design Patterns with pre-flight hardware auto-detection (KVM, graphical display, containers, CUDA/Vulkan GPUs), Tag-as-Select role filtering, and reboot assessment.
- `playbooks/workstation.yml` — full workstation provisioning. Targets the `workstations` group
  (tinybot, gir, soundbot) across modular plays: repositories (import_playbook), common (common), system (tuning, gpu, networking, containerd, theme, gnome, cosmic, sway, libvirt),
  user (user), and tools (tools).

Roles live directly in `roles/`: `common`, `containerd`, `cosmic`, `gnome`, `gpu`, `libvirt`, `nas`, `networking`, `sway`, `theme`, `tools`, `tts`, `tuning`, `user`. Desktop-environment provisioning is split into `theme` (shared wallpapers, icon/GTK themes), `gnome` (GNOME core stack, GDM, extensions), `cosmic` (COSMIC desktop environment and `cosmic-greeter`), and `sway` (Sway/SwayFX compositor and Waybar/Eww), dispatched via the Tier 1 `desktop_environment` SSOT (`none` | `gnome` | `cosmic` | `sway`). Host developer utilities, IDEs (VS Code), Flatpaks, and input-remapper live in `tools`. Coding agent CLIs and the Antigravity Hub & IDE are provisioned by the standalone playbooks in `playbooks/agent-harness/`. The transcribe.cpp (Whisper) transcription CLI is built by the standalone opt-in playbook `playbooks/transcribe-cpp.yml`.


Image building roles and playbooks (`osbuild`, `composer_cli`) and declarative
blueprints have been moved into the standalone `osbuild` repository at
`~/WorkspaceV3/Syncopated/osbuild`. RPM packaging roles and playbooks (`rpm_dev`)
have been moved into the standalone `rpmbuild` repository at
`~/WorkspaceV3/Syncopated/rpmbuild`. AI/LLM operations roles (`dify`, `langfuse`,
`hermes`, `ollama`), dedicated service playbooks (`dify-docker.yml`,
`langfuse-podman.yml`, `hermes.yml`, `ollama.yml`, `remediate.yml`), and the
remediation plugin pipeline have been moved into the standalone `llmops` repository
at `~/WorkspaceV3/Syncopated/llmops`.

Repo-root YAML configuration: `ansible-navigator.yml`, `local.yml` (pull playbook), and the
`argspec_validation_plays*.yml` pair.

## Commands

```bash
# Run main playbook
ansible-playbook playbooks/workstation.yml

# Run specific role only
ansible-playbook playbooks/workstation.yml --tags "base"

# Run pre-flight assertion checks across all roles (fail-fast validation)
ansible-playbook playbooks/workstation.yml --tags "assert" --check

# Lint (from collection dir)
ansible-lint

# Run molecule tests (from collection dir)
molecule test

# Run pre-commit on all files
pre-commit run --all-files

```

## Configuration

- Inventory: `inventory/hosts.yml` (the only inventory; set as the default in `ansible.cfg`)
- Group vars: `group_vars/dev.yml` (and `group_vars/all.yml`)
- Host vars: `host_vars/{{ inventory_hostname }}.yml` (e.g. `host_vars/tinybot.yml`)
- User vars define: `user.name`, `user.home`, `user.shell`
- ansible.cfg enables: fact caching (jsonfile, `/tmp/ansible_cache`), pipelining,
  and the repo-local `llm_analyzer` callback (`profile_tasks` is commented out —
  enabling both means editing the single `callbacks_enabled` line)
- Logs go to `.logs/` and `/tmp/ansible.log`

## Testing & Execution Boundaries

- **CRITICAL: NEVER execute test playbooks or mutation runs directly against the user's host workstation.**
- **All tests, role checks, and playbook validations MUST run inside dev containers, disposable VMs, or Molecule testbeds (e.g. `molecule test`), never on the live workstation.**
- Pre-flight validation checks must always use `--check` mode (`--tags assert --check`) or isolated test environments.

## Testing

- tox-ansible skips Python 3.7/3.8 and ansible-core < 2.14
- molecule scenarios in `extensions/molecule/`
- pytest: `pytest -vvv -n 2` (parallel execution)
- Requires: ansible-core >= 2.15.0

## Linting

Two distinct pre-commit configs — running `pre-commit run --all-files` from the
repo root does **not** apply the collection hooks.

Repo root (`.pre-commit-config.yaml`):
- **black** (line-length=100)
- **isort** (import sorting)
- **flake8** (Python linting)
- **prettier** (YAML/TOML formatting)
- **ansible-lint** (Ansible best practices)

The repository uses a unified pre-commit config.
`update-docs`, `check-merge-conflict`, `check-symlinks`, `debug-statements`,
`end-of-file-fixer`, `no-commit-to-branch`, `trailing-whitespace`,
`add-trailing-comma`, `prettier`, `isort`, `black`, `flake`. Note these do
*not* include `ansible-lint` — run it from the repo root.

## Conventions

- Roles follow standard structure: tasks/, defaults/, vars/, meta/, handlers/
- Distribution-specific tasks in `tasks/distro/{{ ansible_distribution }}.yml`
- Tags: use `tags: ['always']` for critical tasks, domain tags for filtering
- Variable precedence: role defaults < group_vars < host_vars < extra vars

### Variable Naming & Scoping
- **Tier 1 (Host & Domain Scope)**: Semantic, unprefixed names (`user.*`, `desktop_environment`, `enable_third_party_repos`, `workstation_path_dirs`, `workstation_prompt_reboot`) represent machine hardware, primary user identity (SSOT), or system-wide capabilities in `group_vars/` or `host_vars/`. Do NOT force artificial role prefixes onto them, as doing so distorts their semantic meaning and forces redundant multi-role copies. `var-naming[no-role-prefix]` is deliberately skipped in `.ansible-lint` for this reason.
- **Tier 2 (Role Scope)**: Variables defined in role `defaults/main.yml`, `vars/main.yml`, and `set_fact` must be role-prefixed (`<role>_*`) to maintain clean namespaces and avoid cross-role leakage.
- **Task Registrations**: Variables created via `register:` must be role-prefixed (`<role>_*`) because registered variables have global host scope in Ansible and will collide across roles if left generic.

### Firewall & Port Management
- Port and firewall rules are **co-located** within the specific role or application task that requires them (e.g. using `ansible.posix.firewalld`), rather than centralized into a standalone firewall role. This ensures services remain self-contained, modular, and manage their own ingress needs directly.

### Pre-flight Assertions (Fail-Fast Pattern)
- Every role implements a modular `tasks/assert.yml` validating platform compatibility, package manager, init manager, effective root permissions (`id -u == 0` registered as `_<role>_effective_uid`), and identity variables before performing mutations.
- Gated in `tasks/main.yml` by `<role>_assert_enabled | default(true) | bool`.
- All assertion tasks are tagged with `["<role>", "assert", "always"]`.
- Supports standalone pre-flight execution via `--tags assert` or `tasks_from: assert.yml`.

## Repo-local Plugins

Plugin paths are wired in `ansible.cfg` (`library`, `module_utils`,
`callback_plugins`, `filter_plugins`).

- `plugins/callback/` — callback plugins. `llm_analyzer` explains every play and
  task with an LLM on a background worker pool and records each prediction to an
  append-only trace store. See [`plugins/callback/README.md`](plugins/callback/README.md).
- `plugins/callback_utils/` — support modules for `llm_analyzer`. They live
  outside `plugins/callback/` on purpose; see
  [`plugins/callback_utils/README.md`](plugins/callback_utils/README.md) before
  adding a file to either directory.
- `scripts/llm_trainset.py` — builds a DSPy trainset from captured traces and
  scores it (`stats`, `evaluate`, `backfill`, `examples`, `sql`).

## Agent Skills

User skills live in `~/.gemini/skills/<name>/SKILL.md` and are loaded on demand:
- **langfuse** — Langfuse tracing, datasets, evaluation; pairs with the `b08x.llmops.langfuse` role (`~/.gemini/skills/langfuse/SKILL.md`)

**trackboi** is provided via MCP tools rather than a `SKILL.md` file; see the block below.

<trackboi>
## trackboi Skill

When trackboi MCP tools are available, agents can load trackboi skill details, then call `orient_agent` to catch up before updating cards, tracks, boards, or handoff notes. If `.trackboi`, `.etc/.trackboi`, or `.etc/trackboi` files are present but MCP tools are not available, agents may read those files to catch up on local context. Do not manually create, update, or delete trackboi records in the filesystem; use MCP tools for mutations.
</trackboi>

## Empirical Operational & Environmental Guardrails (FCA Invariants)

Based on 3-month session intelligence and Formal Concept Analysis (FCA) forensics across the workstation ecosystem (`workstation`, `osbuild`, `rpmbuild`, `mistral-vibe`):

### 1. Environmental Tooling Guardrails
- **`find` Command Denylist Workaround**: The host environment and sandboxes enforce a security denylist blocking raw `find` executions (`tooling-limitation × environmental` #1 recurring friction, 312+ incidents). Agents MUST NEVER issue raw `find` commands. Use `ls -R`, recursive shell globbing (`shopt -s globstar; ls **/*.yml`), `read_file`, or target-directed python/ruby scripts.
- **YAML Codebase-Memory Fallback**: When querying `codebase-memory-mcp` tools (`search_graph`, `trace_path`) on YAML-first Ansible repositories, knowledge graphs frequently return empty or partial coverage. Agents must immediately execute direct source inspection (`read_file`, `grep`) rather than looping through empty graph queries.
- **Rootless Podman Network Resolution**: In rootless containerized test environments, default IPv6/AAAA lookups fail. Enforce `ip_resolve=4` in container registries and network configurations.
- **Pre-commit Hook Isolation**: Pre-commit hooks (`prettier`, `black`, `isort`, `trailing-whitespace`) frequently auto-fix unrelated files in the working tree. After any pre-commit run, agents must inspect `git status` and immediately unstage/revert out-of-scope files (`git restore --staged <file>` / `git checkout <file>`) to preserve atomic commit boundaries.

### 2. Decision & Collaboration Invariants
- **Mandatory Collaborative Gating on Test Suites (`Target_Test`)**: FCA empirical data demonstrates that unsupervised model autonomy on test harnesses has the highest failure rate (13.6% error, 25.4% correction, 82.0% success), whereas collaborative test design reaches 94.4% success with 0% runtime errors. Any structural additions or changes to test suites, Molecule scenarios, or assertion frameworks must be human-gated (`Collab_Decide`) checkpoints.
- **Fail-Fast Escalation on `State_Blocked` / `State_Error`**: Post-failure trajectory tracking shows that autonomous self-retry after `State_Blocked` fails 35.5% of the time, and after `State_Error` fails 42.2% of the time. If an agent task blocks or fails twice consecutively, agents MUST immediately escalate to the user or request guidance rather than persisting in autonomous retry loops.

### 3. Multi-Agent Delegation & Handoff Contracts
- **Rich State Payloads (Eliminating "Thin Handoffs")**: Context loss shifted from memory compaction to thin subagent briefs (`context-loss ×13`). All delegated subagent briefs MUST include explicit state payloads:
  1. Exact file paths (`PATHS`) to inspect or mutate.
  2. Concrete deterministic verification commands (`GATE`).
  3. Pinned type and structural contracts (`CONTRACTS`).

