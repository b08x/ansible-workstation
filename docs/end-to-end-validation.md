# End-to-End Validation: What the Syncopated Pipeline Proves

This document walks one request all the way home — from a sentence describing an
operating system, through a compiled ISO and a KVM install, to a freshly
converged host sitting at the exact threshold of yadm. Each stage is stated as
a material process with its input, transformation, output, and circumstance;
the certainty of every material claim is calibrated to the evidence in the
table near the end; the User's Path states design intent, not observation.
Nothing here is asserted on vibes — the pipeline is boring on purpose,
and the boredom is the proof.

---

## The Scenario *(Material Processes — high certainty per stage; the continuous composition is validated at the seams and inferred between them)*

The syncopated pipeline **transforms** a natural-language description of a
workstation ISO **into** a pristine, yadm-ready host, **through** six stages
(the last validated only to its threshold), **within** two hard constraints: the
build host must be Fedora or an EL 10 distribution, and the declared disk size
must not exceed the real disk — a smaller disk aborts the install.

**Technical contract**

- **Input** — a natural-language request naming distro, hardware stack,
  hardening profile, disk size, users, and locale; at the tail, a dotfiles
  repository URL.
- **Process** — clarify → write intent → validate intent → generate blueprint +
  build script → compile ISO → install in KVM (kickstart, zero interaction) →
  ansible-pull converges the system → the firstboot hook hands off to yadm.
- **Output** — a blueprint and build script that produce `<name>-<commit>.iso`
  — bootable and zero-interaction-installable by kickstart contract and VM
  harness, with the build itself left to you; and, after installation and
  convergence, a pristine host: system layer converged, yadm installed,
  firstboot hooks deployed, no dotfiles cloned.
- **Circumstance** — the build host is Fedora or EL 10; the role defaults to
  generate-only, so a human runs the build script; LUKS (`disk.encrypt: true`)
  makes the passphrase the installer's only prompt.

There is a particular satisfaction in watching a sentence become a machine, and
this pipeline earns that satisfaction honestly: every handoff between stages is
a concrete artifact — an intent file, a blueprint, a build script, an ISO, a
firstboot hook, an ansible-pull entry point — so you can stop at any seam and
check the work.

## The Pipeline *(Material Processes — staged)*

**Stage 1 — Intent authoring.** Transforms a natural-language request into a
validated *intent file* (`profiles/<name>.yml`) — so named because it declares
what you want the image to be, never how to build it — through the syncopated
skill's clarify-and-copy workflow: at most three clarifying questions (image
kind, distro, hardware/hardening/disk/users), then copy the closest
`profiles/examples/*.yml` and edit only intent fields. The intent is validated
against `schema/intent.schema.json` (JSON Schema draft-07; `additionalProperties:
false`, so a typo in a field name fails validation; every other field is
pattern-, enum-, or range-checked) with required fields `name`, `distro`,
`arch`, `hostname`, `components`, `hardening`, `disk`, `users`, `locale`. The
distro pattern admits `rocky-(9|10).N`, `almalinux-(9|10).N`, and `fedora-N`;
`arch` is `x86_64` only; `hardening` is one of `none | cis-l2-workstation |
pci-dss | hipaa`; `disk.size_gib` is an integer from 32 to 65536.

**Stage 2 — Blueprint generation.** Transforms the intent into an osbuild
blueprint (`<name>.toml`) and a build script (`build-<name>.sh`), **as the
agent runs** `ansible-playbook playbooks/build.yml -e @profiles/<name>.yml`
against the `builder` group. The play's pre-tasks validate the intent
(`ansible.utils.validate`), assert the build host is Fedora or EL 10, resolve
the git commit, and assert `image-builder list` knows the requested distro and
image type; then `roles/osbuild` renders the blueprint from components and
injects the firstboot files, Flathub, repositories, the release file,
hardening, **and remote logging when the intent enables it**, the installer
kickstart, and passwordless sudo for wheel **when the role variable
`osbuild_kickstart_sudoers` is set (off on the intent path)**.
The default mode is *generate-only* (`osbuild_only_generate: true`): the role
writes files and stops.

**Stage 3 — ISO compilation.** Transforms the blueprint into a bootable ISO
(`<name>-<commit>.iso`), through the generated build script: repository preflight
→ `sudo image-builder build` → newest-image discovery → copy to the output
directory. The agent never runs this step; you do — and you run the install
after it, too (the role prints the `virt-install --cdrom` command for you). It
is the seam the generate-only default is built around.

**Stage 4 — KVM installation.** Transforms the ISO into an installed system on
disk, on **a KVM-capable host** (the build host or any machine with /dev/kvm,
qemu-system-x86_64, OVMF and libguestfs), **as you run** `virt-install --cdrom`
(or the unattended harness `tests/vm/run-install-test.sh`: QEMU with
`-enable-kvm` and OVMF, an NVMe disk of exactly `disk.size_gib`, the ISO as
CD-ROM, `-no-reboot`, and zero input). The
kickstart — Anaconda's answer file, which is what makes the install ask nothing
— selects the disk in `%pre` (excluding install media, removable, read-only, and
USB; NVMe first, then largest), checks `disk.serial`, aborts if the disk is
smaller than `disk.size_gib`, and counts down 30 seconds on tty8; any key
aborts. The only prompt is the LUKS passphrase when `disk.encrypt: true`. First
login uses the password `syncopated`, with a forced change (`chage -d 0`); root
stays locked unless `root.enabled`.

**Stage 5a — System convergence via the staged bootstrap (validated on the
rebuild path).** The rebuild orchestrator pushes `scripts/bootstrap.sh` over
SSH to a stock Fedora Server install. Bootstrap step 1 (`scripts/bootstrap.sh`)
installs prerequisites (`git`, `ansible-core`, `ansible-posix`,
`community-general`, `python3-dnf`, `python3-rich`), runs
`dnf upgrade -y --refresh`, writes the step-2 runner and a one-shot systemd
unit (`TimeoutSec=0`), enables it, and reboots. Bootstrap step 2
(`scripts/syncopated-bootstrap-root.sh`) runs `ansible-pull --tags system
local.yml`, which probes hardware (`/dev/kvm`, default target, CUDA, Vulkan)
and converges the repository configuration and the `common`, `tuning`,
`networking`, and `tools` roles unconditionally; `containerd` and `desktop_ui`
unless their enable flags are overridden (both default on); and `libvirt` only
when `/dev/kvm` is present — including installing the yadm RPM (with a
standalone-binary fallback) and deploying the firstboot hooks — then writes
`/var/log/syncopated-stage2.done`, self-disables, and reboots.

**Stage 5b — First login on an osbuild-built ISO (unvalidated composition).**
The injected splash (`roles/osbuild/files/firstboot/syncopated-firstboot`) runs
`sudo dnf upgrade`, sets the graphical target, and runs `ansible-pull` only if
the image carries `/etc/syncopated-ansible-pull.conf` — which an intent-built
image does not (see What This Does Not Validate). The osbuild-ISO convergence
composition is not validated.

**Stage 6 — Firstboot handoff *(design; validated to the threshold)*.**
On the validated rebuild path, transforms the converged system into a
yadm-ready user environment, through `syncopated-firstboot`
(`ws/scripts/syncopated-firstboot`) — the *firstboot*
hook, so named because it runs once, at first login: it prompts for a dotfiles
repository (default `https://github.com/b08x/dots.git`), validates it with
`git ls-remote`, **re-prompting until the URL answers (exiting non-zero in auto
mode)**, runs `yadm clone -f --no-bootstrap`, then `yadm bootstrap`, and
writes `~/.local/state/syncopated/firstboot.done`.

> The validated endpoint of this document is the **threshold** of Stage 6 — the
> *pristine checkpoint*, ready for yadm — not the completed dotfiles convergence.
> That is the next walk.

## The User's Path *(Mental Processes — medium certainty)*

The path is shaped as a short, trust-building sequence: you state requirements
in plain language and learn to trust the clarify step, which asks at most three
questions and skips whatever the request already says… — each clause traceable
to the skill doc (table row L33–100). What they learn, and what they decide:

- They learn to state requirements in plain language and to trust the clarify
  step, which asks at most three questions and skips whatever the request
  already says.
- They learn the intent schema by editing only intent fields — and they learn
  that a typo in a field name fails validation, which I take as a comfort,
  because the schema is strict (`additionalProperties: false`).
- They learn the generate-only default: the workflow writes the blueprint and
  the build script but does not run the build. That decision stays with the
  user, which I find a genuine comfort, because the build — like the install
  that follows it — is never run on your behalf.
- They decide the disk size (declare at most the real size, or the install
  aborts), the hardening profile (`none | cis-l2-workstation | pci-dss |
  hipaa`), and whether to encrypt (which makes the passphrase the installer's
  only prompt).
- They learn the three-layer model — OSBuild, Ansible, yadm — and what "pristine,
  ready for yadm" actually means: system converged, yadm installed, firstboot
  hooks deployed, and no dotfiles cloned yet.
- At firstboot they decide which dotfiles repository to clone, and the script
  validates it with `git ls-remote` before cloning.

## System Architecture *(Relational Processes)*

Three repositories, three layers, three handoffs — one of which points
backward — plus a packaging companion (`rpmbuild`) off the critical path.

- **Layer 0 — OSBuild** (immutable base image) ← the `osbuild` repository. It
  produces the ISO and arms Layer 1 through the first-login splash it injects.
- **Layer 1 — Ansible** (host orchestration) ← the `workstation` repository.
  `local.yml` converges the system layer; the `common` role installs yadm and
  deploys the firstboot hooks.
- **Layer 2 — yadm** (user dotfiles) ← the dotfiles repository (e.g.
  `https://github.com/b08x/dots.git`). Its `01-ansible-pull.sh` bridges back into
  Layer 1.

How they connect:

- The osbuild repository's ISO **arms** Layer 1 **through** the first-login
  splash it injects (`roles/osbuild/files/firstboot/syncopated-firstboot` —
  distinct from the workstation hook of the same name, which later overwrites
  it at the same path): at first graphical login it updates the system and runs
  `sudo ansible-pull` **only if** the image carries
  `/etc/syncopated-ansible-pull.conf`, which no intent field can create.
- The workstation repository's `common` role **enables** Layer 2 **by** installing
  the yadm binary and deploying `/usr/local/bin/syncopated-firstboot` with its
  autostart and profile.d launchers.
- The dotfiles repository's `01-ansible-pull.sh` **re-enters** Layer 1
  (`ansible-pull --tags user local.yml`), so Layer 2 triggers Layer 1 convergence
  before applying user configuration.
- Layer ownership **holds the seams together**: Single Ownership (one
  authoritative manager per file), No Template Clobbering (Ansible never
  overwrites yadm-tracked `$HOME` files), Separation of Binaries and Dotfiles,
  and Fail-Fast Preconditions (every role frontloads assertions).

That is the runtime architecture.

Two companions sit outside the runtime layers. The 6-phase agent workflow
(Specifier → Implementer → Cleaner → Hardener → QA → Architect) is the
meta-loop over the workstation repository; the Specifier phase crosses into
the osbuild repository to design the image, and the remaining phases operate
on the workstation repository. The `rpmbuild` repository is the packaging
companion: when a role needs a custom RPM, work crosses over there; it
supports Layer 1 but sits off this pipeline's critical path.

## Evidence & Measurements

Repo prefixes: `ws/` = `/home/b08x/WorkspaceV3/Syncopated/workstation/`;
`osb/` = `/home/b08x/WorkspaceV3/Syncopated/osbuild/`.

| Claim | Certainty | Evidence (file + line) |
|---|---|---|
| Natural-language → intent workflow (clarify ≤3 questions, copy example, edit intent fields only) | High | `osb/.agents/skills/syncopated/SKILL.md` L33–100 (steps 1–2) |
| Intent schema: required fields, distro pattern, hardening enum, `arch` = `x86_64` only, `disk.size_gib` 32–65536, `additionalProperties: false` | High | `osb/schema/intent.schema.json` L9–61 |
| Intent validation: `ansible.utils.validate`, fail naming offending fields, map intent → role vars, assert component files exist | High | `osb/roles/osbuild/tasks/intent.yml` L23–94 |
| Build play: `hosts: builder`, `become: true`, pre-tasks (intent validate, Fedora/EL10 assert, git commit, `image-builder list` assert), `roles: [osbuild]` | High | `osb/playbooks/build.yml` L24–89 |
| Generate-only default (`osbuild_only_generate` defaults `true`) | High | `osb/roles/osbuild/tasks/select_build_mode.yml` L8–13 |
| Blueprint rendering (components, firstboot, Flathub, repos, hardening + remote logging, kickstart, passwordless sudo) | High | `osb/roles/osbuild/tasks/blueprint.yml`: components L7–24; firstboot splash injection L33–72; Flathub L74–96; Rocky repos L98–118; release L120–122; hardening + remote logging L124–160; kickstart L162–231; sudoers L232–238; TOML check L240–272 |
| Remote logging (schema block, blueprint injection, role defaults; off by default) | High | `osb/schema/intent.schema.json` L144–158; `osb/roles/osbuild/tasks/blueprint.yml` (Inject hardening and remote logging files); `osb/roles/osbuild/defaults/main.yml` (Remote Logging) |
| Completion summary (FINISHED branch) prints a `virt-install --cdrom` test command; the default GENERATED branch (L274–283) prints only the build instruction | High | `osb/roles/osbuild/tasks/main.yml` L262–272, L274–283 |
| Build script: repo preflight, `sudo image-builder build`, newest image, copy to `<name>-<commit>.iso` | High | `osb/roles/osbuild/templates/image-builder-build.sh.j2` (88 lines) |
| Build hosts: `builder` = `gir` (Fedora, local, .10) + `tinybot` (AlmaLinux 10, SSH .11) | High | `osb/inventory/hosts.yml` L6–14 |
| ISO install: zero-interaction kickstart, `%pre` disk pick (NVMe first, then largest), 30 s tty8 countdown, LUKS-only prompt | High | `osb/.agents/skills/syncopated/SKILL.md` L127–137 ("What the generated ISO does") |
| Injected first-login splash: `sudo dnf upgrade`, graphical target, `ansible-pull` only when `/etc/syncopated-ansible-pull.conf` is present | High | `osb/roles/osbuild/files/firstboot/syncopated-firstboot` (conf-conditional ansible-pull lines) |
| First-login password `syncopated`, forced change (`chage -d 0`), root locked unless `root.enabled` | High | `osb/roles/osbuild/defaults/main.yml` L248–261 |
| Unattended KVM install harness: `-enable-kvm`, OVMF, NVMe disk of exactly `disk.size_gib`, `-no-reboot`, zero input; offline libguestfs + online `syncopated-scan` | High | `osb/tests/vm/run-install-test.sh` L1–55 (header), 210 lines |
| `local.yml` two plays: system (`become: true`, tags) + user (`become: false`, tag `user`) | High | `ws/local.yml` L22–37, L410–417 |
| Hardware probes (`/dev/kvm`, default target, CUDA, Vulkan) gate `libvirt`, `desktop_ui`, `containerd` enablement | High | `ws/local.yml` pre-flight capability detection block |
| Stage 1 bootstrap: prerequisites, `dnf upgrade`, Stage 2 runner + systemd unit, enable, reboot | High | `ws/scripts/bootstrap.sh` L34–156 |
| Stage 2: `ansible-pull --tags system local.yml`; done marker; self-disable; reboot | High | `ws/scripts/syncopated-bootstrap-root.sh` L27–43 |
| yadm installed by `common` role (RPM via DNF, standalone fallback, assert present) | High | `ws/roles/common/tasks/yadm.yml` L4–53; included at `ws/roles/common/tasks/main.yml` L70–72 |
| Firstboot hooks deployed (`/usr/local/bin/syncopated-firstboot`, launcher, autostart `.desktop`, profile.d `.sh`), gated on `common_firstboot_enabled` default `true` | High | `ws/roles/common/tasks/firstboot.yml` L13–64; gate `ws/roles/common/tasks/main.yml` L74–77 |
| Stage 3 firstboot: prompt dotfiles repo (default `dots.git`), `git ls-remote` validate, `yadm clone -f --no-bootstrap`, `yadm bootstrap`, `firstboot.done` marker | High | `ws/scripts/syncopated-firstboot` L17, L49–81 |
| yadm → ansible bridge: `01-ansible-pull.sh` defaults (workstation repo, `local.yml`, `development`), opt-in `SYNCOPATED_ANSIBLE_PULL`, runs `ansible-pull --tags user local.yml` | High | `ws/scripts/01-ansible-pull.sh` L38–44, L57–66, L92–110 |
| Three-layer taxonomy + layer ownership principles | High | `ws/docs/layering-architecture.md` L1–78 |
| 6-phase agent workflow (Specifier → Implementer → Cleaner → Hardener → QA → Architect) as the meta-loop over the workstation repository | High | `ws/.agents/skills/syncopated/SKILL.md` §3 |
| `rpmbuild` repository as packaging companion (supports Layer 1, off this pipeline's critical path) | High | `ws/.agents/skills/syncopated/SKILL.md` §1 companion table; `rpmbuild/README.md` |
| `fedora-minimal-vm-rebuild` done condition (8 points, incl. idempotency `changed=0, failed=0`) | High | `ws/goals/fedora-minimal-vm-rebuild/goal.md` L9–20 |
| Rebuild orchestrator: 8-step pipeline (teardown → kickstart → virt-install → await SSH → Stage 1 → Stage 2 → Stage 3 → verify idempotence) | High | `ws/goals/fedora-minimal-vm-rebuild/rebuild-orchestrator.sh` L1–60 (config), 417 lines |
| `ks.cfg` unattended minimal (`@core` + `openssh-server`, Btrfs, user `b08x`, root locked) | High | `ws/goals/fedora-minimal-vm-rebuild/ks.cfg` L1–57 |
| Vagrantfile: libvirt/KVM provider, `almalinux` (primary) + `fedora` VMs | Medium | `ws/Vagrantfile` L1–45, 231 lines |
| A single continuous run spanning both repositories end to end | Low (inferred) | Seams only: ISO (Stage 3), firstboot hook (Stages 4–5), ansible-pull entry (Stage 5); no single continuous-run log cited |

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
- **System convergence on an osbuild-built ISO.** The intent schema has no
  field that arms the ISO's first-login splash
  (`/etc/syncopated-ansible-pull.conf` is written only from the
  `osbuild_ansible_pull_repo`/`osbuild_ansible_pull_args` role variables, which
  intents cannot set), and the staged bootstrap is validated only when the
  rebuild orchestrator invokes it over SSH on a stock Fedora Server ISO. An
  intent-built ISO installed by hand updates itself at first login, installs
  yadm to `~/.local/bin`, and prints the clone/bootstrap commands — it does not
  converge. That composition is unvalidated.
- **The osbuild ISO does not trigger the staged bootstrap.** Nothing the
  blueprint injects (first-login splash, Flathub, repos, release file,
  hardening, kickstart, sudoers) runs `bootstrap.sh`; the staged bootstrap is
  the rebuild-orchestrator's mechanism.
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
- On the validated rebuild path, an installed host converges its system layer
  via `ansible-pull --tags system local.yml` — orchestrator-triggered over SSH
  — and lands at a pristine checkpoint: yadm installed, firstboot hooks
  deployed, no dotfiles cloned.
- Idempotency verified on the rebuild path (**stock Fedora Server ISO,
  orchestrator-driven**): a second `local.yml` pass reports `changed=0,
  failed=0`.
- The host is ready for yadm: clone your dotfiles, run `yadm bootstrap`, and
  Layer 2 takes it from there.

And there it rests — a machine that has done everything a machine should do,
and has the good manners to stop just before it does anything that is yours.
That threshold is a small thing, and it is very nearly the whole point. I am
grateful to the pipeline for stopping there; it leaves the best part to you.
