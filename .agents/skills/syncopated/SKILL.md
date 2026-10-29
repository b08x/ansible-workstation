---
name: syncopated
description: Project management skill for the Syncopated Workstation Ansible control repository. Covers the full provisioning lifecycle — auditing roles against 15 design patterns, writing and refactoring roles/playbooks, pre-flight assertions, tag-as-select filtering, variable scoping, testing (ansible-lint, molecule, --check), and the 6-phase agent workflow pipeline (Specifier → Implementer → Cleaner → Hardener → QA → Architect). References the osbuild companion repo for image/blueprint building in the Specifier phase.
---

# Syncopated Workstation Skill

Manage the Syncopated Workstation Ansible control repository: audit roles,
write and refactor playbooks, enforce conventions, verify changes, and
coordinate the 6-phase agent workflow pipeline. This skill is the operational
companion to `ansible-patterns-anti-patterns` — it tells you **how** to work
in this repo; the patterns skill tells you **what good looks like**.

---

## 1. Project Orientation

### What This Is

An Ansible control repository for provisioning Fedora, AlmaLinux, and Rocky
Linux workstations. Ten roles, layered playbooks, and `local.yml` at the root
for `ansible-pull` convergence. Built and maintained with AI coding agents.

### Where Things Live

| Path | Contents |
|------|----------|
| `AGENTS.md` | Project conventions, commands, testing, variable scoping |
| `roles/` | Ten roles: `common`, `tuning`, `networking`, `containerd`, `libvirt`, `desktop_ui`, `tools`, `user`, `nas`, `tts` |
| `playbooks/` | `workstation.yml` (full provisioning), `repositories.yml`, `nas.yml`, `tts.yml` |
| `local.yml` | Root-level `ansible-pull` entry point (pull-based convergence) |
| `inventory/` | `hosts.yml`, `group_vars/`, `host_vars/` |
| `docs/` | Architecture, conventions, usage, build process, failure points |
| `goals/` | PDCA-style goal tracking (goal.md, facts.md, plan.md per goal) |
| `plugins/callback/` | `llm_analyzer.py` (opt-in LLM trace), `rich_ci_formatter.py` |
| `scripts/` | Bootstrap stages, ansible-pull bridge, DSPy trainset builder |

### Companion Repositories

| Repository | Purpose | When to Cross Over |
|-----------|---------|-------------------|
| `~/WorkspaceV3/Syncopated/osbuild` | Image building: declarative blueprints, ISO/appliance/disk composition | Specifier phase — designing custom OS images |
| `~/WorkspaceV3/Syncopated/rpmbuild` | RPM packaging: `rpm_dev` role, mock build chroots | Packaging custom RPMs for roles |
| `~/WorkspaceV3/Syncopated/llmops` | LLM operations: Dify, Langfuse, Hermes, Ollama | Deploying LLM services on provisioned hosts |

### Hosts

| Host | Role | Connection |
|------|------|------------|
| `gir` | Fedora dev workstation (builder) | local |
| `tinybot` | AlmaLinux builder target | SSH (192.168.41.11) |
| `soundbot` | Workstation target | SSH |
| `ninjabot` | Headless server | SSH |

---

## 2. Hard Rules (from AGENTS.md)

1. **Never auto-commit.** Show the diff, offer the commit, wait for explicit request.
2. **Variable scoping**:
   - **Tier 1** (host/domain): Unprefixed names in `group_vars/`/`host_vars/` (`user.*`, `enable_desktop`, `use_containers`, `use_kvm`)
   - **Tier 2** (role-scoped): Role-prefixed in `defaults/`, `vars/`, `set_fact` (`<role>_*`)
   - **Registered variables**: Always role-prefixed (`register: _<role>_result`)
3. **Every role has `tasks/assert.yml`** — fail-fast pre-flight validation. Gated by `<role>_assert_enabled | default(true) | bool`. Tagged `["<role>", "assert", "always"]`. Run with `--tags assert`.
4. **One file, one owner.** Before templating a shared config path, grep for other writers.
5. **Idempotency**: every skip-if-present guard ships with a matching `*_force_install` override variable.
6. **Atomic commits**: one logical change per commit. Classify by intent (`feat`, `fix`, `refactor`, `chore`, `revert`, `docs`).
7. **Layer boundary**: Ansible (Layer 1) never writes into `$HOME` paths that yadm (Layer 2) owns.

---

## 3. The 6-Phase Workflow Pipeline

Adapted from the SwarmForge workflow matrix for Ansible project management.
Each phase has a gate — work does not proceed until the gate passes.

```
Phase 1: SPECIFIER    →  Design roles, playbooks, variables, image blueprints
Phase 2: IMPLEMENTER  →  Write tasks, templates, defaults, handlers
Phase 3: CLEANER      →  Refactor to 15 patterns, reduce complexity, DRY
Phase 4: HARDENER     →  Add assertions, run lint, security scan, idempotency check
Phase 5: QA           →  ansible-lint, molecule, --check, --tags assert
Phase 6: ARCHITECT    →  Pattern compliance audit, dependency direction, layer boundaries
```

### Phase 1 — Specifier (Design + Image Blueprints)

**Cognitive strategy**: Translate requirements into role/playbook designs,
variable schemas, and (when needed) osbuild blueprints for custom images.

**Key activities**:
- Read the goal/request and produce a design document
- Identify which roles are affected
- Define Tier 1 variables (group_vars/host_vars) and Tier 2 variables (role defaults)
- For custom OS images: cross over to `~/WorkspaceV3/Syncopated/osbuild` and write
  an intent file under `profiles/` validated against `schema/intent.schema.json`
- Produce a Gherkin-style acceptance checklist (Given/When/Then) for the change

**Gate**: Design document reviewed. Variable names follow scoping rules.
Acceptance criteria are testable. No implementation code written yet.

### Phase 2 — Implementer (Write)

**Cognitive strategy**: Write production tasks, templates, defaults, and
handlers until the acceptance criteria pass.

**Key activities**:
- Write `tasks/*.yml` following the Task Dispatcher Pattern (Pattern 1)
- Write `defaults/main.yml` for overridable config, `vars/main.yml` for internal data
- Use `include_vars` for distro-switching (Pattern 3, Dialect A)
- Add `tags` to every task (Pattern 7)
- Add `backup: true` to every `template`/`copy` (Pattern 8)
- Use blocks for grouped conditions (Pattern 9)
- Write `handlers/main.yml` with only handlers that are notified (Pattern 14)
- Add `debug: msg: "Starting <role> tasks"` entry message (Pattern 13)

**Gate**: All acceptance criteria pass. `ansible-playbook --check --tags assert`
succeeds. No lint errors.

### Phase 3 — Cleaner (Refactor)

**Cognitive strategy**: Eliminate duplication, enforce the 15 patterns,
reduce complexity. Match code to the canonical pattern forms.

**Key activities**:
- Run the per-role violation matrix from `ansible-patterns-anti-patterns`
- Fix violations: missing tags, missing backups, hardcoded values, dead handlers
- Extract repeated filter chains into shared variables
- Move hardcoded package lists to `vars/{{ ansible_distribution }}.yml`
- Standardize feature flag dialect: `var | default(false) | bool == True`
- Ensure `defaults/main.yml` has overridable config; `vars/main.yml` has internal-only data

**Gate**: Violation matrix shows zero new violations. `ansible-lint` passes.
`ansible-playbook --check` still succeeds.

### Phase 4 — Hardener (Assertions + Security)

**Cognitive strategy**: Add fail-fast pre-flight assertions, enforce
idempotency, scan for security issues.

**Key activities**:
- Ensure `tasks/assert.yml` exists and validates: platform compatibility,
  package manager, init manager, effective root permissions (`id -u == 0`
  registered as `_<role>_effective_uid`), identity variables
- Gate assertions in `tasks/main.yml` with `<role>_assert_enabled | default(true) | bool`
- Tag all assertion tasks with `["<role>", "assert", "always"]`
- Verify idempotency: every skip-if-present guard has a `*_force_install` override
- Check firewall rules are co-located in the role (Pattern 15 — data-driven, not hardcoded)
- Verify layer boundary: no writes to `$HOME` paths owned by yadm

**Gate**: `ansible-playbook playbooks/workstation.yml --tags assert --check` passes
for all roles. No security regressions.

### Phase 5 — QA (Verify)

**Cognitive strategy**: Run the full verification suite. Prove the change works.

**Key activities**:
```bash
# Pre-flight (no mutations)
ansible-playbook playbooks/workstation.yml --tags "assert" --check

# Lint
ansible-lint

# Syntax check
ansible-playbook playbooks/workstation.yml --syntax-check

# Dry run on target
ansible-playbook playbooks/workstation.yml --check --diff

# Molecule tests (per role)
cd roles/<role> && molecule test

# Pre-commit hooks
pre-commit run --all-files
```

**Gate**: All commands pass. Zero lint violations. Molecule tests green.
Check mode reports expected changes only.

### Phase 6 — Architect (Pattern Compliance + Governance)

**Cognitive strategy**: Audit the change against the 15 patterns, verify
dependency direction, enforce layer boundaries, and assess cross-role impact.

**Key activities**:
- Run the per-role violation matrix — confirm no new violations
- Check dependency direction: roles should not import from other roles' internals
- Verify variable scoping: Tier 1 unprefixed, Tier 2 role-prefixed
- Check that firewall rules are data-driven (Pattern 15)
- Verify tag coverage: every `import_tasks`, `template`, `copy`, `file` has tags
- Assess blast radius: which hosts, groups, and playbooks are affected
- Update `goals/<goal-name>/` with facts and progress

**Gate**: Zero new pattern violations. Variable scoping correct. Tag coverage
complete. Impact assessment documented.

---

## 4. Common Commands

```bash
# Full provisioning
ansible-playbook playbooks/workstation.yml

# Specific role only
ansible-playbook playbooks/workstation.yml --tags "tools"

# Pre-flight assertions only (no mutations)
ansible-playbook playbooks/workstation.yml --tags "assert" --check

# Pull-based local convergence
ansible-pull -U <repo-url> --tags system local.yml
ansible-pull -U <repo-url> --tags user local.yml

# Lint
ansible-lint

# Molecule tests (from role dir)
cd roles/common && molecule test

# Pre-commit on all files
pre-commit run --all-files

# Syntax check
ansible-playbook playbooks/workstation.yml --syntax-check

# Dry run with diff
ansible-playbook playbooks/workstation.yml --check --diff
```

---

## 5. Variable Scoping Quick Reference

| Tier | Location | Prefix | Examples |
|------|----------|--------|----------|
| Tier 1 (host/domain) | `group_vars/`, `host_vars/` | None (semantic) | `user.name`, `user.home`, `enable_desktop`, `use_containers`, `use_kvm`, `enable_third_party_repos` |
| Tier 2 (role-scoped) | `defaults/main.yml`, `vars/main.yml`, `set_fact` | `<role>_` | `common_assert_enabled`, `tools_force_install`, `desktop_ui_theme` |
| Registered | `register:` in tasks | `_<role>_` | `register: _tools_effective_uid` |

**Precedence**: role defaults < group_vars < host_vars < extra vars

---

## 6. The 15 Patterns Quick Reference

See `ansible-patterns-anti-patterns` skill for the full catalogue with
per-role violation matrices. Summary:

| # | Pattern | One-Line Rule |
|---|---------|---------------|
| 1 | Task Dispatcher | `main.yml` imports subtask files with `when` guards |
| 2 | Data-Driven Dirs | Create dirs from a definitions list with overridable defaults |
| 3 | Distro-Switching | Use `include_vars` for >2 distro branches; `when` for ≤2 |
| 4 | Git+Template+Compose | Full lifecycle: clone → template → stop → create |
| 5 | Pre-flight Check | Detect capabilities before roles execute (KVM, GPU, display) |
| 6 | Role Composition | Layer playbooks: repos → common → system → user → tools |
| 7 | Tag-as-Select | Every task has at least one tag; role name = primary tag |
| 8 | Backup-on-Write | Every `template`/`copy` to a config file has `backup: true` |
| 9 | Block-as-Unit | Group related tasks with shared `become`, `when`, or `ignore_errors` |
| 10 | Environment Injection | Set `environment:` at play level; don't copy-paste |
| 11 | Feature Flags | Use `var \| default(false) \| bool == True` consistently |
| 12 | Post-task Lifecycle | `post_tasks` for reboot/cleanup only, not firewall rules |
| 13 | Debug-as-Progress | `debug: msg: "Starting X tasks"` at role entry (or consistently absent) |
| 14 | Handler Notification | Every handler is notified; no dead handlers |
| 15 | Data-Driven Firewall | Firewall ports from variable lists, not hardcoded |

---

## 7. Verification Checklist

Before reporting any change as complete:

- [ ] `ansible-playbook playbooks/workstation.yml --tags "assert" --check` passes
- [ ] `ansible-lint` passes with zero violations
- [ ] `ansible-playbook playbooks/workstation.yml --syntax-check` passes
- [ ] Every `import_tasks` has a `tags` list (Pattern 7)
- [ ] Every `template`/`copy` has `backup: true` (Pattern 8)
- [ ] `defaults/main.yml` contains overridable config; `vars/main.yml` contains internal-only data
- [ ] Distro-switching uses `include_vars` consistently (Pattern 3)
- [ ] Feature flags use `var | default(false) | bool == True` (Pattern 11)
- [ ] No handlers defined without a corresponding `notify` (Pattern 14)
- [ ] No `post_tasks` in playbooks do work that belongs in a role (Pattern 12)
- [ ] Debug entry message exists (Pattern 13)
- [ ] Firewall ports are variable-driven (Pattern 15)
- [ ] Variable scoping: Tier 1 unprefixed, Tier 2 role-prefixed
- [ ] Registered variables are role-prefixed (`_<role>_*`)
- [ ] Layer boundary respected: no writes to `$HOME` paths owned by yadm
- [ ] `pre-commit run --all-files` passes
- [ ] Idempotency: every skip-if-present guard has a `*_force_install` override

---

## 8. Goal Tracking (goals/ Directory)

Each goal lives in `goals/<goal-name>/` with:

| File | Purpose |
|------|---------|
| `goal.md` | The objective, success criteria, scope |
| `facts.md` | Discovered facts about the current state |
| `facts.meta.json` | Metadata about fact gathering |
| `facts-result.json` | Raw fact-gathering results |
| `facts-review.json` | Reviewed and validated facts |
| `plan.md` | Step-by-step implementation plan |
| `interview.json` | Structured interview/elicitation data |
| `interview-result.json` | Processed interview results |

When starting work on a goal, read `goal.md` first. Update `facts.md` and
`plan.md` as work progresses. Mark completion in `goal.md`.

---

## 9. Reporting

When reporting on completed work:

1. **What changed** — files created/modified, roles affected
2. **Which phase** — where in the 6-phase pipeline the work sits
3. **Verification results** — which checks passed, which were skipped and why
4. **Pattern compliance** — any violations introduced or fixed
5. **Impact** — which hosts, groups, and playbooks are affected
6. **Next steps** — what phase comes next, or what the user should do

Never commit unless explicitly asked. Show the diff first.
