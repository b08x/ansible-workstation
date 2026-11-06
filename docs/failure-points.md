# Failure Points & What They Taught

This is the section I care about most. Every entry below is a real failure that
occurred during the build of this repository, extracted from the session
friction logs. Each one taught a pattern that is now encoded in this repository
— as code, lint rules, pre-flight assertions, or documented conventions.

The mix matters as much as the count: some of these failures are about systems,
and some are about how to talk about systems — never auto-commit (5), a
speaker's own hedge (7), commit-message shell quoting (22) — and both kinds
became rules. The conventions in [`conventions.md`](conventions.md) are these
failures, generalized — the return edge, stated here where the failures live.
The newest addendum: a fail-fast preflight can deadlock the very migration
meant to clear it (23).

For the build process that produced these failures, see
[`build-process.md`](build-process.md).

---

## The 23, at a glance

1. [Never restart zram on a device holding live swap](#1-never-restart-zram-on-a-device-holding-live-swap)
2. [One file, one owner](#2-one-file-one-owner)
3. [A detection result that is never used is a latent bug](#3-a-detection-result-that-is-never-used-is-a-latent-bug)
4. [Seat-filtered session detection for display-manager restarts](#4-seat-filtered-session-detection-for-display-manager-restarts)
5. [Never auto-commit](#5-never-auto-commit)
6. [Prettier invalidates line-wrapped match strings](#6-prettier-invalidates-line-wrapped-match-strings)
7. [A speaker's own hedge is a hard exclusion signal](#7-a-speakers-own-hedge-is-a-hard-exclusion-signal)
8. [dnf5 boolean options accept multiple spellings — and that breaks idempotency](#8-dnf5-boolean-options-accept-multiple-spellings--and-that-breaks-idempotency)
9. [Confirm the failing host before local probing in multi-host Ansible](#9-confirm-the-failing-host-before-local-probing-in-multi-host-ansible)
10. [Presence checks need an escape hatch](#10-presence-checks-need-an-escape-hatch)
11. [YAML folded scalars do not interpret `\n`](#11-yaml-folded-scalars-do-not-interpret-n)
12. [Role-scoped variables need the role prefix](#12-role-scoped-variables-need-the-role-prefix)
13. [Atomic commits are a discipline, not a preference](#13-atomic-commits-are-a-discipline-not-a-preference)
14. [Missing CDI spec silently breaks NVIDIA container GPU access](#14-missing-cdi-spec-silently-breaks-nvidia-container-gpu-access)
15. [pip --user and uv tool create duplicate conflicting installations](#15-pip---user-and-uv-tool-create-duplicate-conflicting-installations)
16. [Ansible's Jinja2 sandbox lacks `list.append()`](#16-ansibles-jinja2-sandbox-lacks-listappend)
17. [Ansible defaults with Jinja2 expressions evaluate lazily](#17-ansible-defaults-with-jinja2-expressions-evaluate-lazily)
18. [Implicit ordering dependencies between roles break silently](#18-implicit-ordering-dependencies-between-roles-break-silently)
19. [NVIDIA CUDA EL repositories are major-version keyed](#19-nvidia-cuda-el-repositories-are-major-version-keyed)
20. [Pre-commit hooks can block the very first commit](#20-pre-commit-hooks-can-block-the-very-first-commit)
21. [Vagrant CLI breaks when asdf Ruby shadows system gems](#21-vagrant-cli-breaks-when-asdf-ruby-shadows-system-gems)
22. [Multi-line commit messages with angle brackets break zsh parsing](#22-multi-line-commit-messages-with-angle-brackets-break-zsh-parsing)
23. [A fail-fast preflight that deadlocks its own migration](#23-a-fail-fast-preflight-that-deadlocks-its-own-migration)

---

### 1. Never restart zram on a device holding live swap

**What happened**: A handler ran `systemctl restart systemd-zram-setup@zram0`
while the device held 5 GiB of live swap. The kernel rejects writes to
`/sys/block/zram0/comp_algorithm` once the device is initialized, and `ExecStop`
could not reset the device because `swapoff` on a busy device fails. The result:
`EBUSY`, a failed unit, and a broken play.

**The learning**: Apply zram configuration changes at boot, not via live
restart. The `tuning` role's `zram.yml` now defers config application to the
next reboot, with a comment documenting the EBUSY rationale. Losing live-tuning
capability is a small price for not corrupting a running system's swap.

**Pattern**: When a kernel resource cannot be safely reconfigured at runtime,
defer to boot. The cost is a delay; the alternative is a failure.

### 2. One file, one owner

**What happened**: Two roles (`base` and `tuning`) both templated
`/etc/systemd/zram-generator.conf` with different content — `memtotal/2` in one,
`min(ram, 8192)` in the other. Every playbook run overwrote the other's config,
so the file flapped depending on role execution order. Idempotency was defeated
not by a bug in either role, but by the absence of an ownership rule.

**The learning**: The `base` role's zram task was deleted. `tuning` is now the
sole owner of `zram-generator.conf`. Before adding a template task for any
shared path, grep for other writers.

**Pattern**: Assign exactly one role as owner for any managed config file.
Idempotency is a property of ownership, not just of task logic.

### 3. A detection result that is never used is a latent bug

**What happened**: The Intel oneAPI probe checked `test -f
/opt/intel/oneapi/compiler/latest/bin/icx` and set `backend=sycl` when the file
existed. But the CMake configure step never received `-DCMAKE_CXX_COMPILER` or
the oneAPI environment, so it compiled with the default GNU compiler, which
cannot compile SYCL code. The probe correctly detected a real install; the build
ignored the result.

**The learning**: The probe was redesigned to test *usability* — source
`setvars.sh`, try `icpx` → `dpcpp` → `icx`, require `--version` to succeed, and
emit the resolved compiler name. That name is then wired into
`-DCMAKE_CXX_COMPILER` and the build environment. Detection and consumption are
now the same pipeline.

**Pattern**: Capability probes must test usability (execute the tool), and their
result must be wired into the consuming step. Tightening the probe alone only
downgrades the host and masks the real bug.

### 4. Seat-filtered session detection for display-manager restarts

**What happened**: A `Restart GDM` handler restarted the display manager
unconditionally whenever notified, which would kill active graphical sessions
on a managed workstation — including the session of the person running the
playbook.

**The learning**: The handler chain was restructured into three steps, all
listening on the same topic: (1) detect seat sessions via `loginctl
list-sessions` filtered on a non-empty `seat` column, (2) gate the GDM restart
on that list being empty, (3) if sessions exist, show a per-user `zenity
--info` dialog via `runuser -u <user> -- env DISPLAY=:0 ...`. The seat column
distinguishes local graphical logins from SSH and service sessions — SSH
sessions have no seat, so remote automation doesn't block a restart it wouldn't
disrupt.

**Pattern**: When gating display-manager or session-level restarts, filter
`loginctl` output on the seat column rather than counting users via `who`, which
includes SSH sessions.

### 5. Never auto-commit

**What happened**: An agent completed a README change and ran `git add` / `git
commit` unprompted as a natural completion step. The user interrupted the flow
to impose a standing policy: never auto-commit.

**The learning**: Commit history is the repository owner's public authorship
surface. Exercising it without request exceeds delegated scope, even when the
change itself is wanted. The working-tree diff is shown; the commit is offered,
not performed.

**Pattern**: In any session — prose, code, or configuration — stop at showing
the diff and status. Make every `git add` and `git commit` an explicitly
requested action.

### 6. Prettier invalidates line-wrapped match strings

**What happened**: After `prettier --prose-wrap preserve --write` reformatted
the README, python3 splice scripts using exact multi-line match strings failed
with anchor assertion errors — the formatter had re-flowed line breaks, moving
words across line boundaries.

**The learning**: After a formatter has run, never match on exact line-wrapped
text. Use stable paragraph-span anchors (find a start phrase and an end phrase,
splice between), single-line unique markers, or append at end-of-file.

**Pattern**: Formatters change line breaks; match strings that depend on line
breaks are brittle. Anchor on semantic content, not whitespace.

### 7. A speaker's own hedge is a hard exclusion signal

**What happened**: While dictating source material for documentation, the user
offered "probably at least 20 different moving parts" but immediately
disclaimed recall. The agent initially included the number in prose; the user
rejected it.

**The learning**: The figure was dropped entirely. The one number the speaker
owned — "five to ten thousand virtual machines" — was kept. An unowned number is
fabrication regardless of how plausible it sounds.

**Pattern**: Treat a speaker's own hedge as a hard exclusion signal. Drop the
figure, or keep it with the hedge printed on the record.

### 8. dnf5 boolean options accept multiple spellings — and that breaks idempotency

**What happened**: The repo had `fastestmirror=True` in `dnf.conf`, and an edit
changed it to `fastestmirror=1`. Both are valid per `dnf5.conf(5)` — the boolean
type accepts `1`, `0`, `True`, `False`, `yes`, `no` — but the change caused one
non-idempotent `changed` run (triggering `dnf makecache`) before settling.

**The learning**: Cosmetically valid is not the same as idempotent. The
`fastestmirror` plugin config task was also removed entirely — on dnf5,
fastestmirror is a core `[main]` option and the plugin file is dead
configuration.

**Pattern**: When a config value has multiple valid spellings, pick one and hold
it. A change that is technically correct but causes a non-idempotent run is
still a change that shouldn't happen.

### 9. Confirm the failing host before local probing in multi-host Ansible

**What happened**: A probe on host `gir` returned `rc=1` for a oneAPI check that
must have passed in the run, creating an apparent contradiction. The actual
failure was on `tinybot` (192.168.41.11) — a separate machine with its own oneAPI
install. `gir` had a different, partially broken oneAPI layout.

**The learning**: In multi-host playbooks, verify which host the failure
belongs to (inventory, `host_vars`, run banner) before running diagnostic
probes. SSH to the target host for state that must match the run.

**Pattern**: Multi-host debugging starts with "which host?" — not with "what's
wrong?"

### 10. Presence checks need an escape hatch

**What happened**: The `desktop_ui` role added idempotency guards that skip
installs when a target is already present (theme files, VS Code). But there was
no way to force a reinstall when the present-but-broken state was stale.

**The learning**: Every skip-if-present guard ships with a matching
`*_force_install` default variable at the same time. Both are documented in the
role README, in the same atomic commit.

**Pattern**: Idempotency guards that skip installs need an explicit override
variable, otherwise users cannot recover from a stale present state.

### 11. YAML folded scalars do not interpret `\n`

**What happened**: A `zenity --info` dialog text in a YAML folded scalar (`>-`)
contained `\n` intended as a line break, which would have displayed as the
literal characters backslash-n inside the dialog.

**The learning**: YAML block scalars preserve backslash sequences literally.
Write multi-line dialog text as actual YAML line structure or keep it
single-line.

**Pattern**: Inside YAML block scalars, never rely on `\n` escapes. The escape
lives in the shell, not in the YAML.

### 12. Role-scoped variables need the role prefix

**What happened**: Handler variables registered as `gdm_session_user` and
`gdm_session_uid` would have violated the repo convention that Tier 2
(role-scoped) variables carry the role name prefix.

**The learning**: Every variable defined inside a role is prefixed with the
role name (`desktop_gdm_seat_sessions`, `desktop_gdm_session_user`) before
`ansible-lint` review. This prevents collisions between roles that might
register variables with the same generic name.

**Pattern**: In this repository, role-scoped variables are namespaced by role
prefix. It is a lint rule, but it is also a correctness rule — Ansible registered
variables have global host scope.

### 13. Atomic commits are a discipline, not a preference

**What happened**: Multiple sessions encountered staged diffs that mixed
unrelated changes — a NAS exports move alongside a CPU frequency change, a
theme restructure alongside a new force-install toggle. In each case, the agent
had to decompose the diff into logical units.

**The learning**: One logical change per commit. When a diff touches unrelated
subsystems, split it. When a diff adds a new user-facing variable alongside
restructuring, classify it as `feat` — the new capability dominates the
classification. When a change undoes a prior commit, classify it as `revert`.

**Pattern**: Atomic commits are how you make git history useful. A commit that
mixes a fix and a feature cannot be reverted piecemeal. A commit that mixes two
unrelated fixes cannot be bisected.

### 14. Missing CDI spec silently breaks NVIDIA container GPU access

**What happened**: The NVIDIA container toolkit was installed but `nvidia-ctk
cdi generate` was never run. Containers started successfully but saw no GPU —
a silent failure that looked like a working deployment.

**The learning**: NVIDIA container GPU support requires both toolkit
installation AND CDI spec generation. The CDI spec must exist before containers
can access the GPU; its absence fails quietly.

**Pattern**: "The service started" is not "the service works." Verify the
end-to-end capability, not just the installation.

### 15. pip --user and uv tool create duplicate conflicting installations

**What happened**: The same Python packages were installed via both `pip
--user` and `uv tool`, creating duplicate, conflicting installations that were
fragile across Python version changes.

**The learning**: Prefer `uv` for consistency and isolation. `pip --user`
installations are fragile across Python version changes; `uv` manages its own
environments with hardlink caching that eliminates disk duplication.

**Pattern**: One package manager per layer. Mixing managers for the same
packages creates a reconciliation problem with no owner.

### 16. Ansible's Jinja2 sandbox lacks `list.append()`

**What happened**: A template attempted `{% set items = items.append(x) %}` and
failed — Ansible's Jinja2 sandbox does not expose `list.append()`.

**The learning**: Use the namespace pattern: `{% set ns = namespace(list=[]) %}`
then `{% set ns.list = ns.list + [item] %}`. It is the standard workaround for
dynamic list building in Ansible templates.

**Pattern**: Ansible's Jinja2 is sandboxed. When a template needs mutable state,
use `namespace()` — it is the supported escape hatch.

### 17. Ansible defaults with Jinja2 expressions evaluate lazily

**What happened**: A role's `defaults/main.yml` referenced a variable via a
Jinja2 expression, but that variable was set via `set_fact` later in the role.
Depending on evaluation order, the default either saw the old value or an
undefined variable.

**The learning**: Avoid referencing variables in `defaults/` that are set via
`set_fact` later. Either default to `[]` and override in `set_fact`, or compute
the value in `vars/main.yml` (evaluated at parse time) or use a `pre_tasks`
block to ensure the variable exists early.

**Pattern**: Ansible's lazy evaluation means "where a variable is defined"
matters as much as "what it is defined as." Defaults that depend on runtime
state are a bug class, not a style issue.

### 18. Implicit ordering dependencies between roles break silently

**What happened**: A role's `tasks/main.yml` referenced a variable that was
set by a *different* role's `set_fact` in a prior play. When the play order
changed (or the roles were used independently), the variable was undefined and
the play failed.

**The learning**: Role dependencies must be explicit — either through `meta/main.yml`
`dependencies`, through documented variable contracts in the role README, or by
moving shared state to `group_vars`/`host_vars` (Tier 1) rather than relying on
`set_fact` side effects.

**Pattern**: `set_fact` variables have global host scope but no visibility.
If Role B depends on a variable set by Role A, that dependency must be declared,
not discovered.

### 19. NVIDIA CUDA EL repositories are major-version keyed

**What happened**: A templated NVIDIA CUDA repository URL hardcoded a minor
RHEL version path. When the target distribution was AlmaLinux 10 or Rocky Linux
10 (both RHEL 10 derivatives), the repository path was wrong and package
installation failed.

**The learning**: Normalize NVIDIA EL repository paths to the *major* RHEL
version and verify the key filename against the live repository before
templating it. Third-party repos for EL derivatives change their path structure
across major versions.

**Pattern**: When templating third-party repository URLs across distro releases,
verify both the repository endpoint and the release-specific signing key. A path
that works on Fedora does not necessarily translate to EL derivatives.

### 20. Pre-commit hooks can block the very first commit

**What happened**: A new project's pre-commit hooks (ansible-lint, black,
isort) ran on the initial commit and failed — there was nothing to lint yet, or
the hooks themselves had configuration issues. The first commit could not land.

**The learning**: For new projects, either configure pre-commit hooks to allow
the initial commit, or use `--no-verify` for the first commit and let the hooks
engage from the second commit onward.

**Pattern**: Pre-commit hooks assume a working baseline. The first commit *is*
the baseline; the hooks should not gate its creation.

### 21. Vagrant CLI breaks when asdf Ruby shadows system gems

**What happened**: After installing a Ruby version manager (asdf), the Vagrant
CLI — which relies on distro-packaged Ruby gems — failed because asdf's Ruby
shadowed the system Ruby in PATH, and the distro gems were not visible to the
asdf-managed Ruby.

**The learning**: When using version managers like asdf, invoke system tools
that rely on distro gems with a clean PATH (e.g., `PATH=/usr/bin:/bin vagrant`)
or adjust the version manager's shim configuration.

**Pattern**: Version managers that shadow system toolchains create invisible
dependency gaps. The tool is installed; the libraries it needs are not visible
to it.

### 22. Multi-line commit messages with angle brackets break zsh parsing

**What happened**: A `git commit -m "... Co-Authored-By: Name <email>"` with
double quotes failed in zsh with a parse error near `>`, because the shell
interpreted the angle brackets as redirection operators.

**The learning**: Use single quotes for commit messages containing special
characters, or pass attribution via the `--author` flag instead of embedding it
in the message body.

**Pattern**: Shell quoting rules apply to commit messages. A message that parses
in bash may not parse in zsh.

### 23. A fail-fast preflight that deadlocks its own migration

**What happened**: The Negativo 17 provider mutual-exclusion preflight
(`roles/gpu/tasks/assert.yml`) fails when more than one NVIDIA driver provider
is configured. Legacy hosts carry exactly that conflict (official CUDA repo +
RPM Fusion driver set), and the fix — the hard-break migration in
`roles/gpu/tasks/nvidia.yml` — runs *after* the preflight. Without an exit, a
legacy host fails at assert and the migration can never execute.

**The learning**: A presence/conflict check that blocks remediation of the
state it detects is a deadlock, not a guard. Failing fast is only correct when
the play offers a path that reaches the fix.

**Pattern**: Conflict preflights get an explicit skip override at the same
time they ship (`gpu_nvidia_provider_preflight: false` for the single
hard-break migration run), documented in the role README in the same atomic
commit — the same contract as entry 10, applied to assert-time checks.

