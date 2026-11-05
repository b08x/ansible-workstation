# End-to-End Validation: What the Syncopated Pipeline Proves

This document walks one request all the way home — from a sentence describing an
operating system, through a compiled ISO and a KVM install, to a freshly
converged host sitting at the exact threshold of yadm. Each stage is stated as
a material process; the certainty of every material claim is calibrated to the
evidence in the table near the end; the User's Path states design intent, not
observation. Nothing here is asserted on vibes — the pipeline is boring on
purpose, and the boredom is the proof.

---

## The Scenario *(Material Processes — high certainty per stage; the continuous composition is validated at the seams and inferred between them)*

The syncopated pipeline takes a natural-language description of a workstation
ISO and delivers a pristine, yadm-ready host, in six stages (the last validated
only to its threshold), under two hard constraints: the build host must be
Fedora or an EL 10 distribution, and the declared disk size must not exceed
the real disk — a smaller disk aborts the install.

**Technical contract**

- **Input** — a natural-language request naming distro, hardware stack,
  hardening profile, disk size, users, and locale; at the tail, a dotfiles
  repository URL.
- **Process** — clarify → write intent → validate intent → generate blueprint +
  build script → compile ISO → install in KVM (kickstart, zero interaction) →
  first console login fires firstboot stage 1, whose armed `ansible-pull`
  converges the system → first graphical login fires stage 2, which hands off
  to yadm.
- **Output** — a blueprint and build script that produce `<name>-<commit>.iso`
  — bootable and zero-interaction-installable by kickstart contract and VM
  harness, with the build itself left to you; and, after installation and
  convergence, a pristine host: system layer converged, yadm installed,
  firstboot suite deployed, no dotfiles cloned.
- **Circumstance** — the build host is Fedora or EL 10; the role defaults to
  generate-only, so a human runs the build script; LUKS (`disk.encrypt: true`)
  makes the passphrase the installer's only prompt.

There is a particular satisfaction in watching a sentence become a machine, and
this pipeline earns that satisfaction honestly: every handoff between stages is
a concrete artifact — an intent file, a blueprint, a build script, an ISO, a
firstboot hook, an ansible-pull entry point — so you can stop at any seam and
check the work.

## The Pipeline *(Material Processes — staged)*

**Stage 1 — Intent authoring.** A natural-language request becomes a validated
*intent file* (`profiles/<name>.yml`) — so named because it declares what you
want the image to be, never how to build it. The syncopated skill's
clarify-and-copy workflow asks at most three clarifying questions (image kind,
distro, hardware/hardening/disk/users), then has you copy the closest
`profiles/examples/*.yml` and edit only intent fields. The intent is validated
against `schema/intent.schema.json` (JSON Schema draft-07;
`additionalProperties: false`, so a typo in a field name fails validation; every
other field is pattern-, enum-, or range-checked) with required fields `name`,
`distro`, `arch`, `hostname`, `components`, `hardening`, `disk`, `users`,
`locale`. The distro pattern admits `rocky-(9|10).N`, `almalinux-(9|10).N`, and
`fedora-N`; `arch` is `x86_64` only; `hardening` is one of `none |
cis-l2-workstation | pci-dss | hipaa`; `disk.size_gib` is an integer from 32
to 65536.

**Stage 2 — Blueprint generation.** The intent becomes an osbuild blueprint
(`<name>.toml`) and a build script (`build-<name>.sh`), **as the agent runs**
`ansible-playbook playbooks/build.yml -e @profiles/<name>.yml` against the
`builder` group. The play's pre-tasks validate the intent
(`ansible.utils.validate`), assert the build host is Fedora or EL 10, resolve
the git commit, and assert `image-builder list` knows the requested distro and
image type; then `roles/osbuild` renders the blueprint from components and
injects the firstboot files, Flathub, repositories, the release file,
hardening, **and remote logging when the intent enables it**, the installer
kickstart, and passwordless sudo for wheel **when the role variable
`osbuild_kickstart_sudoers` is set (off on the intent path)**.
The default mode is *generate-only* (`osbuild_only_generate: true`): the role
writes files and stops.

**Stage 3 — ISO compilation.** The blueprint becomes a bootable ISO
(`<name>-<commit>.iso`) through the generated build script: repository preflight
→ `sudo image-builder build` → newest-image discovery → copy to the output
directory. The agent never runs this step; you do — and you run the install
after it, too (the role prints the `virt-install --cdrom` command for you). It
is the seam the generate-only default is built around.

**Stage 4 — KVM installation.** The ISO becomes an installed system on disk, on
**a KVM-capable host** (the build host or any machine with /dev/kvm,
qemu-system-x86_64, OVMF and libguestfs), **as you run** `virt-install --cdrom`
— or the unattended harness `tests/vm/run-install-test.sh`: QEMU with
`-enable-kvm` and OVMF, an NVMe disk of exactly `disk.size_gib`, the ISO as
CD-ROM, `-no-reboot`, and zero input. The kickstart — Anaconda's answer file,
which is what makes the install ask nothing — selects the disk in `%pre`
(excluding install media, removable, read-only, and USB; NVMe first, then
largest), checks `disk.serial`, aborts if the disk is smaller than
`disk.size_gib`, and counts down 30 seconds on tty8; any key aborts. The only
prompt is the LUKS passphrase when `disk.encrypt: true`. First login uses the
password `syncopated`, with a forced change (`chage -d 0`); root stays locked
unless `root.enabled`.

**Stage 5a — System convergence via one privileged pull.** The retired staged
bootstrap (`scripts/bootstrap.sh` → `syncopated-bootstrap-root.service`) has
been removed; a stocked install converges through the same single pull both
other layers use — the `user` role's stage-1 `ansible-pull` (ISO path) or
`yadm bootstrap`'s conditional `bootstrap.d/02-ansible-pull.sh` step (vanilla
path). The pull runs `local.yml`, which probes hardware (`/dev/kvm`, default
target, CUDA, Vulkan) and converges the repository configuration and the
`common`, `tuning`, `gpu`, `networking`, and `tools` roles unconditionally —
the `gpu` role installs vendor stacks only when `intel_oneapi_install` /
`nvidia_cuda_install` host flags are set, otherwise it makes no changes;
`containerd` and `desktop_ui` unless their enable flags are overridden (both
default on); and `libvirt` only when `/dev/kvm` is present — including
installing the yadm RPM (with a standalone-binary fallback) in `common` and,
in the user role, deploying the 7-file firstboot suite byte-identical to the
osbuild SSOT, then writing the machine pull marker `~/.initial-firstboot` (primary workstation user's home)
after a full-tag run.

**Stage 5b — First console login on an osbuild-built ISO.** The kickstart
boots to `multi-user.target`, so the first interactive non-root non-SSH login
on `/dev/tty1` fires stage 1 of the injected two-stage splash
(`roles/osbuild/files/firstboot/syncopated-firstboot --stage 1`, gated on
`~/.initial-firstboot`): it waits for the network, runs
`sudo dnf -y upgrade --refresh`, sets up language toolchains, runs
`sudo ansible-pull` armed by `/etc/syncopated-ansible-pull.conf` (baked by
default now that `osbuild_ansible_pull_repo`/`osbuild_ansible_pull_args` role
defaults are non-empty), verifies the machine marker, sets the default target
to `graphical.target`, and offers a reboot when updates were installed. The
osbuild-ISO convergence composition is not validated (see What This Does Not
Validate).

**Stage 6 — Stage-2 handoff at first graphical login *(design; validated to
the threshold)*.** The rebooted system opens the graphical greeter; the XDG
autostart entry (`/etc/xdg/autostart/syncopated-firstboot.desktop`) launches
stage 2 unless the per-user
`~/.local/state/syncopated/firstboot-stage2.done` marker exists (the legacy
`firstboot.done` marker also counts as done, so already-onboarded users are
never nagged). Stage 2 offers `Run yadm setup now` / `Show commands` /
`Skip for this machine`; running installs yadm to `~/.local/bin` when missing
and executes exactly `yadm clone --bootstrap https://github.com/b08x/dots.git`,
delegating drift preflight and the step registry to the yadm bootstrap
orchestrator; `Skip` writes the marker with a `declined` note and exits
`RC_SKIPPED`(2). By-name runs (`syncopated-firstboot --stage 2`) always show
the offer and commands regardless of markers.

> The validated endpoint of this document is the **threshold** of Stage 6 — the
> *pristine checkpoint*, ready for yadm — not the completed dotfiles convergence.
> That is the next walk.

## The User's Path *(Mental Processes — medium certainty)*

The path is shaped as a short, trust-building sequence — each clause below is
traceable to the skill doc (table row L33–100). What they learn, and what they
decide:

- They learn to state requirements in plain language and to trust the clarify
  step, which asks at most three questions and skips whatever the request
  already says.
- They learn the intent schema by editing only intent fields — and they learn
  that a typo in a field name fails validation, because the schema is strict
  (`additionalProperties: false`), which I take as a comfort.
- They learn the generate-only default: the workflow writes the blueprint and
  the build script but does not run the build. That decision stays with the
  user, because the build — like the install that follows it — is never run on
  your behalf.
- They decide the disk size (declare at most the real size, or the install
  aborts), the hardening profile (`none | cis-l2-workstation | pci-dss |
  hipaa`), and whether to encrypt (which makes the passphrase the installer's
  only prompt).
- They learn the three-layer model — OSBuild, Ansible, yadm — and what "pristine,
  ready for yadm" actually means: system converged, yadm installed, firstboot
  suite deployed, and no dotfiles cloned yet.
- At the stage-2 offer they decide whether to run `yadm clone --bootstrap`
  now, see the commands, or skip for this machine — and the offer never nags
  again once decided, while staying runnable by name.

## System Architecture *(Relational Processes)*

Three repositories, three layers, three handoffs — one of which points
backward — plus a packaging companion (`rpmbuild`) off the critical path.

- **Layer 0 — OSBuild** (immutable base image) ← the `osbuild` repository. It
  produces the ISO and arms Layer 1 through the first-login splash it injects.
- **Layer 1 — Ansible** (host orchestration) ← the `workstation` repository.
  `local.yml` converges the system layer; the `common` role installs yadm, and
  the `user` role owns and deploys the 7-file firstboot suite plus the machine
  pull marker `~/.initial-firstboot` (primary workstation user's home).
- **Layer 2 — yadm** (user dotfiles) ← the dotfiles repository (e.g.
  `https://github.com/b08x/dots.git`). Its `bootstrap.d/02-ansible-pull.sh`
  bridges back into Layer 1, conditionally on the marker.

How they connect:

- The osbuild repository's ISO **arms** Layer 1 **through** the two-stage
  first-login suite it injects (`roles/osbuild/files/firstboot/` — 7 files,
  including `/etc/syncopated-ansible-pull.conf` baked by default from the
  `osbuild_ansible_pull_repo`/`osbuild_ansible_pull_args` role defaults): at
  the first console login stage 1 updates the system and runs
  `sudo ansible-pull`; at the first graphical login stage 2 offers the
  `yadm clone --bootstrap` handoff. When the workstation pull re-deploys the
  suite, it lands byte-identical (parity invariant with the osbuild SSOT).
- The workstation repository's `user` role **enables** Layer 2 **by** deploying
  the firstboot suite (launcher, autostart entry, profile hooks) and installing
  the toolchain surface the yadm bootstrap presupposes.
- The dotfiles repository's `bootstrap.d/02-ansible-pull.sh` **re-enters**
  Layer 1 (one privileged `ansible-pull` against `local.yml`) when
  `~/.initial-firstboot` is absent, so Layer 2 triggers Layer 1 convergence
  before applying user configuration — and skips it when the machine has
  already converged through the same pull (ISO stage 1 or an earlier
  bootstrap).
- Layer ownership **holds the seams together**: Single Ownership (one
  authoritative manager per file), No Template Clobbering (Ansible never
  overwrites yadm-tracked `$HOME` files), Separation of Binaries and Dotfiles,
  and Fail-Fast Preconditions (every role frontloads assertions).

That is the runtime architecture.

One companion sits outside the runtime layers: the `rpmbuild` repository is
the packaging companion — when a role needs a custom RPM, work crosses over
there; it supports Layer 1 but sits off this pipeline's critical path.

## Evidence & Measurements

Repo prefixes: `ws/` = `/home/b08x/WorkspaceV3/Syncopated/workstation/`;
`osb/` = `/home/b08x/WorkspaceV3/Syncopated/osbuild/`.

| Claim | Certainty | Evidence (file + line) |
|---|---|---|
| Intent authoring: copy the closest example from `profiles/examples/` and edit only the fields that matter (name, hostname, `disk.size_gib`, users, locale) | High | `osb/README.md` L56–58 |
| Intent schema: required fields, distro pattern, hardening enum, `arch` = `x86_64` only, `disk.size_gib` 32–65536, `additionalProperties: false` | High | `osb/schema/intent.schema.json` L9–61 |
| Intent validation: `ansible.utils.validate`, fail naming offending fields, map intent → role vars, assert component files exist | High | `osb/roles/osbuild/tasks/intent.yml` L23–94 |
| Build play: `hosts: builder`, `become: true`, pre-tasks (intent validate, Fedora/EL10 assert, git commit, `image-builder list` assert), `roles: [osbuild]` | High | `osb/playbooks/build.yml` L24–89 |
| Generate-only default (`osbuild_only_generate` defaults `true`) | High | `osb/roles/osbuild/tasks/select_build_mode.yml` L8–13 |
| Blueprint rendering (components, firstboot, Flathub, repos, hardening + remote logging, kickstart, passwordless sudo) | High | `osb/roles/osbuild/tasks/blueprint.yml`: components L7–24; firstboot splash injection L33–72; Flathub L74–96; Rocky repos L98–118; release L120–122; hardening + remote logging L124–160; kickstart L162–231; sudoers L232–238; TOML check L240–272 |
| Remote logging (schema block, blueprint injection, role defaults; off by default) | High | `osb/schema/intent.schema.json` L144–158; `osb/roles/osbuild/tasks/blueprint.yml` (Inject hardening and remote logging files); `osb/roles/osbuild/defaults/main.yml` (Remote Logging) |
| Completion summary (FINISHED branch) prints a `virt-install --cdrom` test command; the default GENERATED branch (L274–283) prints only the build instruction | High | `osb/roles/osbuild/tasks/main.yml` L262–272, L274–283 |
| Build script: repo preflight, `sudo image-builder build`, newest image, copy to `<name>-<commit>.iso` | High | `osb/roles/osbuild/templates/image-builder-build.sh.j2` (88 lines) |
| Build hosts: `builder` = `gir` (Fedora, local, .10) + `tinybot` (AlmaLinux 10, SSH .11) | High | `osb/inventory/hosts.yml` L6–14 |
| ISO install: zero-interaction kickstart, `%pre` disk pick (NVMe first, then largest), 30 s tty8 countdown, LUKS-only prompt | High | `osb/README.md` L249–253; `osb/roles/osbuild/README.md` L1057–1063 |
| Injected two-stage splash: stage 1 (`dnf upgrade`, toolchains, armed `ansible-pull` from `/etc/syncopated-ansible-pull.conf`, marker verify, graphical target) + stage 2 (offer `yadm clone --bootstrap`, per-user `firstboot-stage2.done` marker, legacy `firstboot.done` read-compat) | High | `osb/roles/osbuild/files/firstboot/syncopated-firstboot` (`stage1`, `stage2`, stage/marker constants) |
| First-login password `syncopated`, forced change (`chage -d 0`), root locked unless `root.enabled` | High | `osb/roles/osbuild/defaults/main.yml` L248–261 |
| Pull arming defaults now non-empty (`https://gitlab.com/syncopatedX/workstation.git`, `-C development -i localhost, local.yml`) — every firstboot-enabled profile bakes the pull conf | High | `osb/roles/osbuild/defaults/main.yml` L395–396 |
| Firstboot injection idempotence: `blockinfile` marker renders once; 7 suite paths + conditional `/etc/syncopated-ansible-pull.conf` and `/etc/syncopated-user.conf` stanzas | High | `osb/roles/osbuild/tasks/blueprint.yml` (Inject first-login splash files); `osb/roles/osbuild/tests/firstboot/check_injection.py` |
| Unattended KVM install harness: `-enable-kvm`, OVMF, NVMe disk of exactly `disk.size_gib`, `-no-reboot`, zero input; offline libguestfs + online `syncopated-scan` | High | `osb/tests/vm/run-install-test.sh` L1–55 (header), 210 lines |
| `local.yml` two plays: system (`become: true`, tags) + user (`become: false`, tag `user`) | High | `ws/local.yml` L22–37, L465–473 |
| Hardware probes (`/dev/kvm`, default target, CUDA, Vulkan) gate `libvirt`, `desktop_ui`, `containerd` enablement | High | `ws/local.yml` pre-flight capability detection block |
| Workstation-repo firstboot suite: data-driven 7-file deployment (root context) + stat-guarded machine marker writer gated on full-tag `ansible_run_tags` | High | `ws/roles/user/tasks/firstboot.yml` (deploy loop + marker task); gate `ws/roles/user/tasks/main.yml` (include `firstboot.yml`) |
| `local.yml` pre-flight reads the osbuild-baked `/etc/syncopated-user.conf` (`WORKSTATION_USER=`) before the `user.name`/`b08x` fallback chain | High | `ws/local.yml` (Play 1 + Play 2 pre_tasks: probe/slurp/seed `workstation_user`) |
| yadm installed by `common` role (RPM via DNF, standalone fallback, assert present) | High | `ws/roles/common/tasks/yadm.yml` L4–53; included at `ws/roles/common/tasks/main.yml` L70–72 |
| Stage-2 offer: `Run yadm setup now` / `Show commands` / `Skip for this machine`; auto-run delegates to `yadm clone --bootstrap $DOTFILES_URL` and relays its exit code; per-user `firstboot-stage2.done` marker (declined note on Skip) | High | `osb/roles/osbuild/files/firstboot/syncopated-firstboot` (`stage2`, `stage2_run_setup`); parity copy `ws/roles/user/files/firstboot/` |
| Machine pull marker: `~/.initial-firstboot` (primary workstation user's home; `root:root 0644` — phase-4 amendment, `/root` is unstat-able by non-root users), single writer = workstation `roles/user` task, full-tag runs only; stage 1, the profile hook and the yadm step only `test -f` it (no sudo) | High | `ws/roles/user/tasks/firstboot.yml` (marker task); `osb/roles/osbuild/files/firstboot/syncopated-firstboot` (`MACHINE_MARKER`); `/etc/profile.d` hook (`syncopated-firstboot.sh`) |
| yadm → ansible bridge: `bootstrap.d/02-ansible-pull.sh` checks the marker at the top of `main()` (plain `test -f`, no sudo), skips with `RC_SKIPPED`; `SYNCOPATED_ANSIBLE_PULL_FORCE`/`SYNCOPATED_ANSIBLE_PULL_FIRSTBOOT_MARKER` seams | High | dots repo `bootstrap.d/02-ansible-pull.sh` (marker block); `tests/ansible.bats` (marker-present/absent/force/env-override cases) |
| Three-layer taxonomy + layer ownership principles | High | `ws/docs/layering-architecture.md` L1–78 |
| `rpmbuild` repository as packaging companion (supports Layer 1, off this pipeline's critical path) | High | `ws/README.md` L144 (Companion Repositories table) |
| `fedora-minimal-vm-rebuild` done condition (8 points, incl. idempotency `changed=0, failed=0`) | High | `ws/goals/fedora-minimal-vm-rebuild/goal.md` L9–20 |
| Rebuild orchestrator: 8-step pipeline (teardown → kickstart → virt-install → await SSH → Stage 1 → Stage 2 → Stage 3 → verify idempotence) | High | `ws/goals/fedora-minimal-vm-rebuild/rebuild-orchestrator.sh` L1–60 (config), 417 lines |
| `ks.cfg` unattended minimal (`@core` + `openssh-server`, Btrfs, user `b08x`, root locked) | High | `ws/goals/fedora-minimal-vm-rebuild/ks.cfg` L1–57 |
| Vagrantfile: libvirt/KVM provider, `almalinux` (primary) + `fedora` VMs | Medium | `ws/Vagrantfile` L1–45, 231 lines |
| A single continuous run spanning all three repositories | Low (inferred) | Seams only: ISO install (Stage 4), tty1 stage-1 hook (Stage 5), XDG stage-2 launcher (Stage 6); no single continuous-run log cited |

## What This Does Not Validate *(negative capability)*

- **Containers, bootc images, qcow2, and Vagrant boxes.** Those go through
  playbooks, not intent files; this validation covers installer ISOs only.
- **The act of building the ISO.** The workflow is generate-only by default; it
  writes and verifies the blueprint and build script, but a human runs
  `build-<name>.sh`.
- **Rocky bootc.** Explicitly unverified in the skill.
- **Non-x86_64 architectures.** `arch` is `x86_64` only in the schema, and the VM
  harness is x86_64-only.
- **Interactive (hand-driven) installation.** The validated path is kickstart
  zero-interaction; a hand-driven install is not covered.
- **A single continuous run spanning both repositories.** Each repository proves
  its own stages; the composition is validated at the seams (the ISO, the
  injected firstboot hook, the ansible-pull entry point), not by one
  uninterrupted execution. This is the honest boundary of the claim — if you
  want the composed walk proven in one log, that run still has to be done.
- **A completed yadm convergence on an osbuild-built ISO.** The validated end
  state is *ready for* yadm (binary installed, hooks deployed, no dotfiles
  cloned). The `fedora-minimal-vm-rebuild` goal does prove convergence,
  idempotency, and yadm bootstrap — but on a stock Fedora Server ISO, not on an
  osbuild-built one.
- **System convergence on an osbuild-built ISO.** The pull is now armed by
  default (`osbuild_ansible_pull_repo`/`osbuild_ansible_pull_args` role
  defaults are non-empty, so every firstboot-enabled profile bakes
  `/etc/syncopated-ansible-pull.conf`, and a profile may still override either
  key per image), but the composed ISO run — install → tty1 stage-1 pull →
  marker → graphical stage-2 offer — has not been executed end to end in one
  continuous log. Each seam carries its own tests (osbuild bats, injection
  checks, workstation parity), not a composed proof.
- **The staged bootstrap relay is retired.** `scripts/bootstrap.sh`,
  `scripts/syncopated-bootstrap-root.sh`, `scripts/syncopated-firstboot`, and
  `scripts/01-ansible-pull.sh` no longer exist; a stocked install converges
  through the same single pull (`local.yml` directly, or the conditional yadm
  `02-ansible-pull.sh` step). The rebuild orchestrator goal artifacts under
  `goals/fedora-minimal-vm-rebuild/` are historical.
- **Remote logging.** Disabled by default; validated only when explicitly enabled
  with a URL and certificates.
- **Root login.** Locked unless `root.enabled` is set.
- **Oversized disk declarations.** A disk smaller than `disk.size_gib` aborts
  the install; that is a constraint, not a validated recovery.
- **The Vagrant path.** A Vagrantfile exists (libvirt/KVM, `almalinux` + `fedora`
  VMs), but this validation follows the ISO → KVM → orchestrator path.

## Outcome

The validated end state, stated plainly:

- A schema-validated intent, a rendered blueprint, and a build script that
  produce `<name>-<commit>.iso` — bootable and zero-interaction-installable by
  kickstart contract and VM harness, with the build itself left to you (see
  negative capability).
- An installed host converges its system layer via one privileged
  `ansible-pull` run against `local.yml` — stage 1 (ISO path) or the
  conditional `02-ansible-pull.sh` step (vanilla path) — and lands at a
  pristine checkpoint: yadm installed, firstboot suite deployed, machine pull
  marker written, no dotfiles cloned.
- Idempotence verified at the seam level (two-run blueprint renders
  byte-stable; stat-guarded marker; second pull reports zero changes at the
  firstboot tasks), not yet by a composed ISO rebuild log.
- The host is ready for yadm: clone your dotfiles, run `yadm bootstrap`, and
  Layer 2 takes it from there.

Read as interpretation of documented behavior, not as a new claim: the
threshold is the same boundary as No Template Clobbering and never auto-commit
— the system does not do your part, and it does not do your part by design, at
every level.

And there it rests — a machine that has done everything a machine should do,
and has the good manners to stop just before it does anything that is yours.
That threshold is a small thing, and it is very nearly the whole point.
