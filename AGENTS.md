<!--# cspell: ignore SSOT CMDB -->
# AGENTS.md

Ensure that all practices and instructions described by
<https://raw.githubusercontent.com/ansible/ansible-creator/refs/heads/main/docs/agents.md>
are followed.

## Project Structure

Four Ansible Collections under `collections/ansible_collections/b08x/`, each a git submodule:
- **devworkstation** — base, user, desktop (incl. VS Code and the Antigravity Hub/IDE), libvirt, networking, containerd, tuning, run, coding_agents (antigravity CLI, claude, crush, opencode, vibe, skills)
- **llmops** — run, ollama, hermes, dify, langfuse, tts
- **rhel_builder** — composer_cli, osbuild, rpm_dev, run
- **context** — run, plus plugins (action, cache, filter, inventory, lookup, modules, test)

Submodules must be initialized before a first run:

```bash
git submodule update --init --recursive
```

`.gitignore` ignores `collections/ansible_collections/b08x/*` and re-includes each
collection explicitly. Adding a fifth collection requires a matching `!` negation
line there as well as a `.gitmodules` entry — otherwise it is silently untracked.

All playbooks live in `playbooks/`, not at the repo root:

- `site.yml` — full workstation provisioning. Targets the `workstations` group
  (tinybot, gir, soundbot) in two plays: a privileged system play (base, tuning,
  desktop, libvirt, containerd) and an unprivileged user play (user,
  coding_agents).
- `base.yml` — the system play of `site.yml` on its own, for base-only runs.
- `osbuild.yml` — custom image builds via `b08x.rhel_builder.osbuild`. Asserts
  Fedora or AlmaLinux. Targets `osbuild_targets`, defined in
  `inventory/hosts.ini` as a children-group of `builder` (tinybot, gir). The
  group name matches the collection's own `playbooks/osbuild.yml`; its sibling
  `composer_cli.yml` expects `composer_cli_builders`, which this repo does not
  define.
- `dify-docker-ninjabot.yml`, `langfuse-podman-tinybot.yml` — standalone
  single-host deployments.

Repo-root YAML is configuration, not plays: `ansible-navigator.yml` and the
`argspec_validation_plays*.yml` pair.

## Commands

```bash
# Run main playbook
ansible-playbook playbooks/site.yml

# Run specific role only
ansible-playbook playbooks/site.yml --tags "base"

# Build a custom image
ansible-playbook playbooks/osbuild.yml

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

Each of the four collections carries its own config with a larger shared set:
`update-docs`, `check-merge-conflict`, `check-symlinks`, `debug-statements`,
`end-of-file-fixer`, `no-commit-to-branch`, `trailing-whitespace`,
`add-trailing-comma`, `prettier`, `isort`, `black`, `flake`. Note these do
*not* include `ansible-lint` — run it separately from the collection dir.

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
### trackboi Skill

When trackboi MCP tools are available, agents can load `.agents/skills/trackboi/SKILL.md` for details, then call `orient_agent` to catch up before updating cards, tracks, boards, or handoff notes. If `.trackboi`, `.etc/.trackboi`, or `.etc/trackboi` files are present but MCP tools are not available, agents may read those files to catch up on local context. Do not manually create, update, or delete trackboi records in the filesystem; use MCP tools for mutations.
</trackboi>
