# Conventions

These are not stylistic preferences. They are patterns that emerged from
failure points in the build process, now encoded as rules. Each one traces
back to a specific failure documented in
[`failure-points.md`](failure-points.md).

The sessions that produced those failures were run by AI coding agents, and
these rules now govern the agents that extend this repository. The rulebook is
written from the inside. The parenthesized *(Failure point N)* citations refer
to the numbered entries in [`failure-points.md`](failure-points.md).

---

## Variable Scoping

See [`variable-precedence.md`](variable-precedence.md) for the full rules.

- **Tier 1 (Host & Domain)**: Semantic, unprefixed names (`user.*`,
  `desktop_environment`, `enable_third_party_repos`, `workstation_prompt_reboot`) in `group_vars/` or
  `host_vars/`. These represent machine hardware, primary user identity, or
  system-wide capabilities.
- **Tier 2 (Role Scope)**: Variables in role `defaults/`, `vars/`, and public role interfaces
  must be role-prefixed (`<role>_*`). *(Failure point 12, 18)*
- **Task Registrations & Internal State**: Variables from `register:` and private internal facts
  must be role-prefixed with a leading underscore (`_<role>_*`) per refactoring rule R3 (registered
  variables have global host scope) — session handlers in `roles/gnome` and `roles/cosmic` register
  `_gnome_dm_seat_sessions` and `_cosmic_dm_seat_sessions`, resolving `_gnome_dm_session_user`
  and `_cosmic_dm_session_user` rather than bare names like `gdm_session_user`.

## Pre-Flight Assertions

Every role frontloads `tasks/assert.yml` — fail-fast validation (< 1s) on
distribution family, package manager, effective root, and identity variables —
before any mutation. Gated by `<role>_assert_enabled | default(true) | bool`.
Tagged `["<role>", "assert", "always"]`. Standalone execution:
`--tags assert`; across the whole repository,
`ansible-playbook playbooks/workstation.yml --tags assert --check` mutates
nothing.

## Firewall & Ports

Port and firewall rules are co-located within the role or application task that
requires them (`ansible.posix.firewalld`), not centralized into a standalone
firewall role — the `nas` role keeps its rules beside the services they admit,
in `tasks/nfs/firewall.yml` and `tasks/samba/firewall.yml`.

## Atomic Commits

One logical change per commit. Split diffs that touch unrelated subsystems.
Classify by intent: `feat` for new user-facing capability (wins over `refactor`
when a diff adds a new variable), `fix` for bug correction, `refactor` for
non-functional restructuring, `chore` for tooling/config, `revert` for undoing
a prior commit, `docs` for documentation only. *(Failure point 13)*
Commit subjects in this repository follow the `emoji type: summary` shape
(`✨ feat:`, `🔧 chore:`, `📝 docs:`).

## Single Ownership

Each managed config file has exactly one owning role. Before adding a template
task for a shared path, grep for other writers. The `zram-generator.conf` flap
between `base` and `tuning` — two roles templating the same file, each run
overwriting the other — is the canonical case. *(Failure point 2)*

## Idempotency

Re-running a playbook against a converged host reports zero changes. Presence
checks skip redundant installs, and every skip-if-present guard ships with a
matching `*_force_install` override variable — `user_bun_force_install`,
`theme_force_install`, and `common_yadm_force_install` are live
examples. *(Failure points 8, 10)*
