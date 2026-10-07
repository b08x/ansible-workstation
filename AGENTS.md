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
  (tinybot, gir, soundbot) across modular plays: base (base), system (tuning, networking, containerd, desktop, libvirt),
  user (user), and tools (tools).

Roles live directly in `roles/`: `base`, `containerd`, `desktop`, `libvirt`, `nas`, `networking`, `tools`, `tts`, `tuning`, `user`.


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

# Lint (from collection dir)
ansible-lint

# Run molecule tests (from collection dir)
molecule test

# Run pre-commit on all files
pre-commit run --all-files
```

## Configuration

- Inventory: `inventory/hosts.ini` (default) or `inventory/hosts.yml`
- Group vars: `group_vars/dev.yml` (and `group_vars/all.yml`)
- Host vars: `host_vars/{{ inventory_hostname }}.yml` (e.g. `host_vars/tinybot.yml`)
- User vars define: `user.name`, `user.home`, `user.shell`
- ansible.cfg enables: fact caching (jsonfile, `/tmp/ansible_cache`), pipelining,
  and the repo-local `llm_analyzer` callback (`profile_tasks` is commented out —
  enabling both means editing the single `callbacks_enabled` line)
- Logs go to `.logs/` and `/tmp/ansible.log`

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
- **Tier 1 (Host & Domain Scope)**: Semantic, unprefixed names (`user.*`, `intel_oneapi_install`, `enable_third_party_repos`, `use_containers`, `use_kvm`) represent machine hardware, primary user identity (SSOT), or system-wide capabilities in `group_vars/` or `host_vars/`. Do NOT force artificial role prefixes onto them, as doing so distorts their semantic meaning and forces redundant multi-role copies. `var-naming[no-role-prefix]` is deliberately skipped in `.ansible-lint` for this reason.
- **Tier 2 (Role Scope)**: Variables defined in role `defaults/main.yml`, `vars/main.yml`, and `set_fact` must be role-prefixed (`<role>_*`) to maintain clean namespaces and avoid cross-role leakage.
- **Task Registrations**: Variables created via `register:` must be role-prefixed (`<role>_*`) because registered variables have global host scope in Ansible and will collide across roles if left generic.

### Firewall & Port Management
- Port and firewall rules are **co-located** within the specific role or application task that requires them (e.g. using `ansible.posix.firewalld`), rather than centralized into a standalone firewall role. This ensures services remain self-contained, modular, and manage their own ingress needs directly.

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

Repo-local skills live in `.agents/skills/<name>/SKILL.md` and are loaded on demand:
- **trackboi** — project/board/card tracking via MCP (see block below)
- **langfuse** — Langfuse tracing, datasets, evaluation; pairs with the `b08x.llmops.langfuse` role

<trackboi>
## trackboi Skill

When trackboi MCP tools are available, agents can load `.agents/skills/trackboi/SKILL.md` for details, then call `orient_agent` to catch up before updating cards, tracks, boards, or handoff notes. If `.trackboi`, `.etc/.trackboi`, or `.etc/trackboi` files are present but MCP tools are not available, agents may read those files to catch up on local context. Do not manually create, update, or delete trackboi records in the filesystem; use MCP tools for mutations.
</trackboi>
