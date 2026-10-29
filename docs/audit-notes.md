# Audit Notes

Terminology accountability, uncertainty labels, and evidence sourcing for the
documentation in this repository. These notes apply across all documents in
`docs/` and the top-level `README.md`.

---

## Terms Introduced

- *course correction rate* — from code-insights friction taxonomy: the share of
  sessions requiring mid-flight direction changes; borrowed from the analytics
  corpus, not an Ansible term
- *seat session* — logind concept: a session with a non-empty seat column,
  distinguishing local graphical logins from SSH
- *CDI spec* — Container Device Interface: NVIDIA's mechanism for exposing GPUs
  to containers; the spec must be generated, not just the toolkit installed
- *explore-then-build* — workflow pattern from session facet analysis: the
  dominant pattern at 36.7% of sessions, where the agent reads and maps the
  codebase before writing
- *lazy evaluation* — Ansible/Jinja2 term: expressions in `defaults/` are not
  resolved at parse time, so dependencies on `set_fact` variables create
  ordering bugs

## Uncertainty Labels

Session counts, friction metrics, satisfaction ratings, and cost estimates are
drawn from the code-insights corpus (`~/.code-insights/data.db`) filtered to 46
project entries whose paths or names match the workstation/Ansible project
lineage (paths containing `workstation`, `Syncopated/ansible`,
`syncopated/ansible`, `ansible-collection`, `syncopated-ansible`,
`ansible-rhel`, `Syncopated/Archive/Ansible`, `Syncopated/OS`, or names matching
`workstation`, `devworkstation`, `ansible`, `Syncopated`, `OS`, `rhel_builder`).
The corpus captures sessions from specific AI coding tools and may not represent
all development activity on this repository — manual edits, non-AI-assisted work,
and sessions from untracked tools are not in the corpus. What would promote
these to high-modality: a complete export of all development activity, not
just AI-assisted sessions. The project-name matching is heuristic (path and
name LIKE patterns); a project that was renamed or moved without a path
overlap would be missed.

## Evidence

All failure-point narratives, workflow patterns, satisfaction ratings, tool
distributions, and architectural decisions are sourced from code-insights data
extracted from session logs in `~/.code-insights/data.db` (read-only SQLite
queries via `ci-report.js`). The repository structure, role descriptions, and
usage instructions are sourced from the codebase itself (`fd`, `read_file` on
`roles/`, `playbooks/`, `scripts/`, `docs/`, `ansible.cfg`, `local.yml`,
`AGENTS.md`). The project lineage paths are sourced from the `projects` table
in the code-insights database.

## Deviations

None. All codebase claims were gathered within the evidence ladder budget
(self-sourced via `fd`, `read_file`, `bash` on the repository structure) or
from code-insights reports (read-only SQLite queries via `ci-report.js`). The
expanded corpus search (querying across 46 project entries by path and name
patterns) was performed via read-only SQL queries through the `ci-report.js`
query interface.
