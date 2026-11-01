# The Build Process, Deconstructed

A traditional README describes a finished product. This one describes a
*process* — because the process is the product. The repository was built across
512 AI coding sessions spanning 46 project entries and roughly nine months
(January 30 – October 26, 2026). The code-insights corpus preserves the shape
of that work: 24,767 messages, 1,491 learnings, 1,324 architectural decisions,
499 session-level facet analyses, and 352 prompt-quality assessments.

Here is what the build looked like, reconstructed from session logs. For the
failure points that shaped it, see [`failure-points.md`](failure-points.md).

---

## The Project Lineage

The repository has been tracked under many names as it moved through the
filesystem and was restructured. The direct lineage tells the story — 10 of the
46 tracked project entries; the remaining entries account for the balance of 512
sessions:

Read it as what it is: the repository's own memory of being rebuilt. Each path
below is a renaming or restructuring the corpus survived, stitched to its
predecessors by path and name matching — a heuristic, documented in
[`audit-notes.md`](audit-notes.md), that would miss a rename with no path
overlap.

```
/home/b08x/Workspace/ansible-rhel-workstation-builder          (5 sessions, Feb 2026)
/home/b08x/Workspace/OS/ansible-collection-rhel-workstation-builder  (30+17+9 sessions, Feb–May 2026)
/home/b08x/Archive/Workspace/Ansible/syncopated/ansible        (21 sessions, May 2026)
/home/b08x/Workspace/OS/syncopated-ansible                     (8 sessions, May–Jun 2026)
/home/b08x/WorkspaceV3/Syncopated/Archive/Ansible              (50 sessions, Aug 2026)
/home/b08x/WorkspaceV3/Syncopated/ansiblev0.1                  (12 sessions, Aug 2026)
/home/b08x/WorkspaceV3/Syncopated/ansible-collection-pop_os    (8 sessions, Aug 2026)
/home/b08x/WorkspaceV3/Syncopated/ansible-collection-rhel-workstation-builder  (57 sessions, May–Aug 2026)
/home/b08x/WorkspaceV3/Syncopated/ansible                      (56+22+8 sessions, Sep–Oct 2026)
/home/b08x/WorkspaceV3/Syncopated/workstation                  (20 sessions, Sep–Oct 2026) ← current
```

Each path change marks a restructuring: from a flat collection to a structured
repository, from a monolithic role set to modular roles, from a single
distribution focus to multi-distro parity (Fedora, AlmaLinux, Rocky Linux).
The git history inside the current repository carries the same arc in commit
messages — the split of the desktop role, the extraction of `osbuild` and
`llmops` into companion repositories, the adoption of pre-flight assertions
across all roles.

---

## The Arc

The repository started as a monolithic desktop role and was progressively split
into focused units. The git history shows the trajectory:

```
d72b8a8  refactor: split desktop role into desktop_ui, tools, and user
62cfe0e  fix(common): adopt reboot lifecycle for auditd and purge fastestmirror on EL
b566f9f  refactor: remediate Vagrantfile per SIFT audit (14 fixes)
70da6e9  chore: add decode, bake, rubydex, bcrypt_pbkdf to development group
2f35549  docs: rewrite user role README to reflect current scope
```

Each commit is a lesson applied. The split of the desktop role into
`desktop_ui`, `tools`, and `user` was not a stylistic preference — it was a
response to a recurring failure mode: one role trying to own too many concerns,
with tasks for GNOME theming sitting alongside CUDA compilation alongside user
shell configuration. The split happened because the alternative was a role that
no one could reason about.

---

## The Session Rhythm

The corpus holds 512 tracked sessions; 499 carry facet-level analysis, and the
pattern, satisfaction, and rhythm figures below cover those 499. Across those
499, the work followed a recognizable pattern:

1. **Probe** — an agent would check the current state of a host or file before
   making changes (stat guards, version checks, hardware detection)
2. **Fail** — something would go wrong (a service restart on live swap, a
   compiler probe that detected but didn't wire, a handler that killed active
   sessions)
3. **Diagnose** — the agent would trace the root cause (kernel EBUSY semantics,
   missing environment sourcing, seat vs. SSH session detection)
4. **Fix** — the fix would be applied, often with a structural change to prevent
   recurrence (single ownership of config files, reboot-deferred application,
   three-step handler chains)
5. **Record** — the learning would be captured in the commit message, the role
   README, or the architectural decision record

This rhythm repeats at every scale the corpus records: a single failure point —
the zram EBUSY entry, [`failure-points.md`](failure-points.md) #1 — is the five
beats in miniature, and the PDCA cycles in [`docs/pdca/`](pdca/) are the same
rhythm institutionalized.

The course correction rate across these sessions was 53.1% — 265 of 499
analyzed sessions required the agent to change direction mid-flight. 461 of
those 499 sessions involved at least one iteration (an average of 4 iterations
per iterating session). That number sounds high, and it is — but I read it as
encouraging: a course correction means the agent compared what happened against
what it intended and adjusted. The friction was the curriculum.

Across the 499 sessions with facet-level analysis, 488 followed a recognizable
pattern:

| Pattern | Sessions | Share |
|---------|----------|-------|
| explore-then-build | 183 | 36.7% |
| direct-execution | 100 | 20.0% |
| iterative-refinement | 72 | 14.4% |
| plan-then-implement | 66 | 13.2% |
| debug-fix-verify | 54 | 10.8% |
| context-gathering | 10 | 2.0% |
| systematic-debugging | 3 | 0.6% |
| unclassified | 11 | 2.2% |

The dominant pattern — explore-then-build, 36.7% of analyzed sessions — is
consistent with an agent that maps the codebase before writing;
direct-execution, at 20.0%, is consistent with one already familiar with it. The
10.8% debug-fix-verify share is the cost of the failure points documented in
[`failure-points.md`](failure-points.md).

---

## The Tool Distribution

Seven AI coding tools contributed sessions across the project lineage:

| Tool | Sessions | Messages | Avg Msgs/Session | Est. Cost |
|------|----------|----------|-----------------|-----------|
| opencode | 221 | 4,212 | 19.1 | $3.53 |
| mistral-vibe | 104 | 5,942 | 57.1 | $167.81 |
| claude-code | 78 | 8,167 | 104.7 | $1,170.40 |
| antigravity | 65 | 2,038 | 31.4 | $0.09 |
| gemini-cli | 21 | 3,588 | 170.9 | $608.53 |
| crush | 20 | 192 | 9.6 | $0.51 |
| claude-desktop | 3 | 628 | 209.3 | $106.22 |

Summed across the seven tools, the estimated total token cost of the build is
~$2,057. OpenCode contributed the most sessions (43.2%) at 19.1 messages per
session — second-lowest, ahead of only crush (9.6) — consistent with quick,
targeted tasks. Claude Code contributed the most messages (33.0% of the total)
and the highest cost — consistent with deep, long-running work. The `bug_hunt`
session character averaged 310 messages per session across 13 sessions, the
longest-running session character in the corpus, which is what you would
expect: debugging is a conversation, not a transaction.

---

## Outcome Satisfaction

Each of the 499 analyzed sessions carries an outcome rating; the distribution
below is the corpus's own verdict on the work:

| Rating | Sessions | Share |
|--------|----------|-------|
| High | 403 | 80.8% |
| Medium | 70 | 14.0% |
| Low | 19 | 3.8% |
| Abandoned | 7 | 1.4% |

The 7 abandoned sessions and 19 low-satisfaction sessions are the ones I would
most want to read, if the corpus preserved more of their narrative. What I can
say is that the 80.8% high-satisfaction rate across 499 analyzed sessions is, I
would call it, a well-spent build process — and the 19.2% that were not fully
satisfying are where I would look first for learnings.

---

## What the Sessions Were About

The sessions clustered around a few themes:

- **Idempotency and convergence** — making sure re-running a playbook reports
  zero changes (the `common` role carries a Molecule scenario that builds
  containers, converges twice, and fails on any second-run change)
- **Hardware detection** — probing for CUDA, Vulkan, Intel oneAPI/SYCL, and
  wiring the detected compiler into the actual build
- **Handler safety** — ensuring service restarts don't kill active user sessions
- **Atomic commits** — splitting multi-file changes into logical units, each
  independently revertable
- **Documentation truth** — keeping role READMEs in sync with actual task logic
- **Multi-distro parity** — extending Fedora-specific roles to AlmaLinux 10 and
  Rocky Linux 10, with distro-specific variable files loaded via `include_vars`
- **Layer boundary enforcement** — deciding what belongs in Ansible (Layer 1)
  versus yadm (Layer 2) versus containers (the fast layer), and holding the line
  when new tools arrived demanding direct host installation
