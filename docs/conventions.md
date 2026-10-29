# Conventions

These are not stylistic preferences. They are patterns that emerged from
failure points in the build process, now encoded as rules. Each one traces
back to a specific failure documented in
[`failure-points.md`](failure-points.md).

---

## Variable Scoping

See [`variable-precedence.md`](variable-precedence.md) for the full rules.

- **Tier 1 (Host & Domain)**: Semantic, unprefixed names (`user.*`,
  `enable_third_party_repos`, `use_containers`) in `group_vars/` or
  `host_vars/`. These represent machine hardware, primary user identity, or
  system-wide capabilities.
- **Tier 2 (Role Scope)**: Variables in role `defaults/`, `vars/`, and `set_fact`
  must be role-prefixed (`<role>_*`). *(Failure point 12, 18)*
- **Task Registrations**: Variables from `register:` must be role-prefixed
  (registered variables have global host scope).

## Pre-Flight Assertions

Every role frontloads `tasks/assert.yml` — fail-fast validation (< 1s) on
distribution family, package manager, effective root, and identity variables —
before any mutation. Gated by `<role>_assert_enabled | default(true) | bool`.
Tagged `["<role>", "assert", "always"]`. Standalone execution:
`--tags assert`.

## Firewall & Ports

Port and firewall rules are co-located within the role or application task that
requires them (`ansible.posix.firewalld`), not centralized into a standalone
firewall role.

## Atomic Commits

One logical change per commit. Split diffs that touch unrelated subsystems.
Classify by intent: `feat` for new user-facing capability (wins over `refactor`
when a diff adds a new variable), `fix` for bug correction, `refactor` for
non-functional restructuring, `chore` for tooling/config, `revert` for undoing
a prior commit, `docs` for documentation only. *(Failure point 13)*

## Single Ownership

Each managed config file has exactly one owning role. Before adding a template
task for a shared path, grep for other writers. *(Failure point 2)*

## Idempotency

Re-running a playbook against a converged host reports zero changes. Presence
checks skip redundant installs, and every skip-if-present guard ships with a
matching `*_force_install` override variable. *(Failure points 8, 10)*
