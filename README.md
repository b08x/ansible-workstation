<div align="center">

# Ansible for a Workstation

A deliberately boring foundation under a fast-moving ecosystem.

Ansible control repository for provisioning Fedora 44, AlmaLinux 10, and Rocky Linux 10 machines —
system configuration, virtualisation, and container runtimes — from a single
inventory with verified support for Ansible core 2.18–2.20 and Python 3.14.

Kept as a working notebook: the roles, playbooks, and plugins are the current
entries of a decade's experiments, and the git history keeps the earlier
entries. A practice rather than a product — the deliverable is maintained
fluency, not a finished state.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](<https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15%20(verified%202.18--2.20)-black.svg>)](https://docs.ansible.com/ansible-core/devel/)
[![python](https://img.shields.io/badge/python-3.14%20%7C%203.12%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml/badge.svg)](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml)

</div>

## Introduction

Every distribution family is a philosophy wearing a package manager.

The Enterprise Pragmatists — RHEL, Rocky, Alma — sell predictability. Software
should not change for ten years; a bug that breaks a feature is bad, but an
update that changes how a feature behaves is a catastrophe. The Upstream
Innovators — Fedora, Arch, Tumbleweed — run the other way: standing still is
falling behind, and Fedora exists to test what will land in RHEL five years
from now. Choosing between them was never really a question of package
managers. It is a question of alignment: does the worldview of the people
building the operating system match the work you are trying to do on top of it.

Most of my career sat on the upstream side of that line, where the technical
conversation is actively happening. This repository is the record of stepping
across to the pragmatic ground. Not a rejection of the upstream mindset — a
calculated structural alignment. Outsource the churn of the base operating
system, and the creative bandwidth goes to what runs on top of it instead of
to fighting the shifting sands underneath it.

Then the LLM ecosystem moved the spotlight onto exactly this choice. When the
application layer stops executing predictable, hard-coded logic and starts
running non-deterministic prompts, autonomous agent loops, and dynamic tool
calls, the host operating system can no longer afford to be a moving target. A
multi-agent system orchestrates file parsers, Python runtimes, and external
APIs; if the base OS changes behavior under it during a routine update,
debugging a rogue tool call becomes archaeology. Specialized compute is
fragile enough on its own — CUDA toolkits and GPU drivers against kernel
namespaces — without the floor moving too.

The machinery that finally made this cheap is recent. The constraint is not.
bootc, image-based updates, and transactional rollback only reached usable
shape a few years ago, while the constraint itself — a fast-moving workload
needs a floor that does not move — was learned the slow way, across a decade
of CI/CD pipelines and realtime audio workstations. Adopting the image tooling
was not a change of thesis. It was the ecosystem finally shipping the
machinery the thesis always needed.

So this repository runs at two speeds.

The **slow layer** is deliberately boring: idempotent roles, explicit variable
tiers, distributions asserted before anything touches the disk, firewall
rules co-located with the services that need them. Ansible's whole job here is
to keep this layer honest — re-running a playbook against a converged host
should report zero changes.

The **fast layer** is everything that legitimately churns: language models,
agent harnesses, RAG pipelines, tokenizers, the tooling that reinvents itself
weekly. That layer lives in containers and disposable images, walled off from
the host's ABI, free to be reckless precisely because the ground underneath it
is not.

The name is borrowed from music. Syncopation puts the accent where the meter
does not expect it — between the beats, against the pulse — and it only works
because the pulse holds. Nothing in this repository keeps the same time. The
AlmaLinux 10 and Rocky Linux 10 base moves on a ten-year clock, Fedora 44 on a thirteen-month one,
Ansible (core 2.18–2.20 on Python 3.14) whenever a playbook runs, the agent tooling on whatever upstream
shipped this week. Syncopated is the practice of letting those disparate
systems land on their own offbeats without losing the downbeat underneath
them.

Make yourself comfortable. The plumbing below is just the argument,
load-bearing.

## Why This Exists

A workstation is not supposed to be interesting. It is supposed to sit under a
desk, apply its updates, and hold its opinions; the interesting machinery —
the failover clusters, the high-availability proxies, the fleets where a
missing machine is a ticket rather than a Tuesday — lives in other buildings,
staffed by other people, funded by budgets that have never once asked what a
revert costs. The repository sits awkwardly between those worlds: half of it
reads like a dotfiles collection, the other half like a datacenter shrunk in
the wash, and for years this bothered its author, who kept trying to frame
the result as one coherent project and kept noticing that it declined to
converge.

The dotfiles half is easy to inventory and slightly embarrassing to defend.
`roles/tools` carries task files for five coding-agent CLIs — antigravity,
claude, crush, opencode, vibe — alongside bun, go, and a GPU-gated
transcribe.cpp, which is the exact inventory of an enthusiast's dotfiles
repository wearing a `roles/` directory as a disguise; these are tools that
reinvent themselves weekly, and they are provisioned with the same ceremony
as the kernel-adjacent plumbing, because ceremony is the only kind of task
template this house had in stock.

The datacenter half is the compensation, and the compensation is the point.
Every one of the ten roles front-loads a pre-flight `assert.yml` that fails in
under a second on unmet preconditions — distribution family, package
manager, effective root, identity variables — before a single mutation
occurs; `local.yml` implements fifteen distinct design patterns, including
pull-based convergence and hardware auto-detection, so a fresh machine can
introduce itself to the network and be rendered correct without a human typing
at it. This is production-grade paranoia, and the fleet it defends is five
physical machines, one of which is the desk the paranoia is written on. The
patterns were learned the only way such patterns are ever learned — on the
job, on infrastructure that needed to scale laterally: Nashville, 2014,
twenty-one roles across three environments, growth that arrived as more
machines rather than bigger ones, hosts nobody was ever supposed to log into.
There is no academy for this material; the machines multiply, the blame needs
an address, and Ansible is what you reach for once both are true. What keeps
the patterns in shape afterward is a fleet, any fleet; so the workstations
stand in as servers, on the reasonable grounds that a pattern does not care
how many machines are watching it be performed.

The sense of scale was calibrated earlier, and higher, on someone else's
vSphere: a global travel website running, at the time, on five to ten thousand
virtual machines — regional clusters, load balancing, caching, every moving
part wanting its particular care, the whole of it managed in Chef and
versioned in SVN, one of which I still discuss in the past tense with real
feeling. Re-running that estate under Ansible is a thought experiment I was
never assigned, and I have completed it anyway, several times, for nobody.

Absence of a fleet does have one recurring cost, and it is not skill decay.
Reorientation to a cloud console after time away takes about a day — a number
that sounds like a confession and is really a property of the medium. A cloud
console is a newspaper: the grammar is fixed, the headlines change, the
layout rearranges itself inside known boundaries, and fluency is knowing the
grammar rather than memorizing the headlines. The grammar survives the lapse;
the headlines do not; a day is the price of re-subscribing. This repository
is where the grammar gets its exercise — asserted, converged, re-run against
machines that report zero changes — so that the day stays a day instead of
becoming a quarter.

Which is the answer to the framing problem, and the reason the bother was
mislabeled all along. I have been grading a practice against the criteria of
a product: a project ends, a practice persists; convergence is a property of
products, and maintained fluency is the property of practices; nobody faults
a gym for failing to become a body. Nothing here is finished because nothing
here is meant to be — the roles are the current entries and the git history
keeps the earlier ones — and the entire apparatus exists so that when a real
fleet is finally handed over, the only new thing will be the fleet.

### Three genres, one repository

The apparent incoherence dissolves once the parts are sorted by genre rather
than by topic:

- **The surface** — the dotfiles genre. Agent CLIs, user tooling, shell
  environment ([`roles/tools`](roles/tools), [`roles/user`](roles/user), the
  yadm Layer 2). Moves weekly, replaced freely; it is the part visitors
  recognize first and mistake for the point.
- **The gym** — the infrastructure genre. Production patterns rehearsed at
  household scale: fail-fast pre-flight assertions in all ten roles,
  pull-based convergence in [`local.yml`](local.yml), fact caching, the
  observe–remediate–learn loop. The patterns stay warm so reorientation costs
  a day, not a quarter.
- **The notebook** — the record. Git history, the `Lineage` section below, the
  trace store. Drift with a changelog beats drift without one, and it beats
  enforced stasis too.

The genres do not compete; they are the same practice viewed from three
altitudes — what is being held (the surface), what is being exercised (the
gym), and what is being remembered (the notebook).

## What Exists Today

This repository is a notebook. I use it to test current tools and methods
against real hosts and to keep a record of what I found. Nothing in it is
finished; each role, playbook, and plugin is the current entry for an
experiment, and the git history keeps the earlier entries. Practically, it
renders the machines in its inventory from a single declaration — but the
machines are the current instantiation, not the point. The repository is an
archive of blueprints — methods, patterns, known-good configurations — that
can be picked up and pointed at any host list, not only mine.

The state of the entries, facet by facet:

- **Image builds live in a dedicated standalone repository.** The `osbuild`
  machinery — composing Fedora, AlmaLinux, and Rocky Linux ISOs, appliances,
  and container disks from declarative blueprints — has been extracted to
  the standalone [`osbuild`](https://gitlab.com/syncopatedX/osbuild) repository
  alongside the package taxonomy and `package_tracker.py` management tooling.
  Repository GPG keys are fetched locally and verified before any compose;
  the target distribution is asserted before anything touches the host. The base
  image remains the reproducible artifact floor beneath this fleet, decoupled so
  image composition evolves without entangling host configuration runs.
- **RPM package development lives in a dedicated standalone repository.** The
  `rpm_dev` role, mock build chroots, and packaging environments have been
  extracted to the standalone [`rpmbuild`](https://gitlab.com/syncopatedX/rpmbuild)
  repository. Package specs and repo builds iterate in isolated mock
  containers without polluting workstation state.
- **LLMOps and remediation live in a dedicated standalone repository.**
  Dedicated AI application platforms (`dify`, `langfuse`), agent runtimes
  (`hermes`, `ollama`), their dedicated service playbooks, and the autonomous
  LLM diagnose-and-remediate pipeline with mechanical safety guards have been
  extracted to the standalone [`llmops`](https://gitlab.com/syncopatedX/llmops)
  repository. Decoupled from host provisioning, the LLM runtime and its self-healing
  pipeline evolve alongside model updates without risking the workstation baseline.
- **Full workstation provisioning runs on Fedora 44, AlmaLinux 10, and Rocky Linux 10.**
  - [`playbooks/workstation.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/playbooks/workstation.yml) includes four plays — base, system, user, coding agents —
    against the `workstations` group in inventory for multi-host push provisioning.
  - [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) provides an autonomous local pull and convergence playbook
    specifically designed for `ansible-pull` and local bootstrap. It implements the
    15 Ansible Design Patterns with pre-flight hardware auto-detection (KVM, graphical
    display, containers, CUDA/Vulkan GPU acceleration), Tag-as-Select role filtering,
    check-mode safety, and post-flight reboot verification. Execution is decoupled into
    two discrete plays: Play 1 (system, `become: true`) handles privileged hardware and OS
    foundation, while Play 2 (user, `become: false`) provisions unprivileged user environment
    and `uv` Python toolchains without prompting for sudo.
  - **Staged bootstrap lifecycle** orchestrates automated convergence from fresh minimal installations:
    - **Stage 1 (`scripts/bootstrap.sh`)**: Standalone shell script installing minimal prerequisites
      (`git`, `ansible-core`, `python3-dnf`, `python3-rich`), running a full `dnf upgrade -y --refresh`,
      staging `syncopated-bootstrap-root.service`, and triggering an initial reboot.
    - **Stage 2 (`scripts/syncopated-bootstrap-root.sh`)**: Automated post-reboot systemd runner configured
      with `TimeoutSec=0` executing `ansible-pull --tags system local.yml`, writing completion sentinel
      `/var/log/syncopated-stage2.done`, self-disabling, and rebooting into the graphical environment.
    - **Stage 3 (`syncopated-firstboot`)**: Deployed system-wide by [`roles/common`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/common) with autostart
      desktop entries and profile hooks; triggers upon first user login to clone dotfiles via native `yadm`,
      run unprivileged user bootstrap, and mark `~/.local/state/syncopated/firstboot.done`.
  - **Graphical target & native Wayland GDM default on workstations**: [`roles/desktop`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/desktop) enables
    desktop provisioning by default (`enable_desktop: true`), configures GDM with native Wayland
    (`WaylandEnable=true` in `/etc/gdm/custom.conf`), promotes the systemd default target to `graphical.target`,
    and installs native RPMs (such as `input-remapper` on Fedora).
  - **Native RPM packaging in the Syncopated COPR (`b08x/syncopated`)**: delivers clean, native RPMs for
    `yadm`, `gitflow`, `gum`, and `uv` across Fedora and Enterprise Linux 10, eliminating reliance on
    unverified GitHub downloads or user-space curl pipelines.
  - Integrated with Yadm bootstrap via `01-ansible-pull.sh`, which acts as an automated
    orchestration bridge: on fresh machine onboarding, Yadm triggers `01-ansible-pull.sh` to
    converge Layer 1 host packages and services via [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) before executing user dotfiles (Layer 2).
  - A strict distribution taxonomy is codified in [`docs/layering-architecture.md`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/docs/layering-architecture.md),
    partitioning duties across OSBuild (Layer 0), Ansible (Layer 1), and Yadm (Layer 2). Detailed bootstrap
    mechanisms are documented in [`docs/bootstrap.md`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/docs/bootstrap.md).
  - **Local virtualization testing via [`Vagrantfile`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/Vagrantfile)**: provides a dedicated libvirt Fedora workstation
    VM definition (`vagrant up fedora`) supporting customizable box releases (`FEDORA_BOX`) for rapid, isolated testing.
  - All 10 roles frontload pre-flight assertions (`tasks/assert.yml`) to fail fast (< 1s)
    on unmet preconditions (OS family, DNF/DNF5 package manager, effective root elevation
    via `id -u`, and identity variables) before mutations occur.
  - System-level utilities (`bun` and GPU-gated `transcribe.cpp` supporting CUDA and Vulkan backends)
    live natively in [`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools). Transcribe compilation is skipped automatically on hosts without
    detected GPU devices (`tools_transcribe_require_gpu: true`).
- **Observability runs in both directions.** The `llm_analyzer` callback
  records what every play and task actually does to an append-only trace
  store, and `scripts/llm_trainset.py` turns those traces into a scored DSPy
  trainset; `rich-ci-formatter` renders the same runs for the human at the
  terminal — DNF5 transaction tables, systemd transitions, phase banners.
  The formatter works; its failure path is the owed polish: a failed task
  currently obscures more than it shows.
- **Testing exists where the risk lives.** The [`common`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/common) role carries a Molecule
  scenario that builds Fedora and AlmaLinux containers, converges twice, and
  fails on any second-run change. Everything lints.
- **bootc is direction, not state.** The image-transaction path is designed
  for, walked partway; the dnf baseline carries the weight today.

What is owed is polish, not function: check-mode idempotency, fail-fast assertions (< 1s),
and end-to-end autonomous convergence via [`local.yml`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/local.yml) and Yadm `01-ansible-pull.sh` are fully verified
across Fedora 44, AlmaLinux 10, and Rocky Linux 10. The remaining polish is in the `rich-ci-formatter`
failure path and a recorded end-to-end demonstration. The evidence so far is convergence on real hosts
and the trace store, not a screencast.

## Intent

One decision, applied consistently, is the whole architecture: the base does
not move, so everything above it is allowed to. The intents are recorded
explicitly, layer by layer, because the parts only make sense as a whole.

### Layers

A strict three-tier taxonomy governs distribution across tooling (see [`docs/layering-architecture.md`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/docs/layering-architecture.md)):

- **The image — the floor (Layer 0).** Kernel, drivers, container runtimes, and the base package set. Built,
  never mutated in place; a change is a new artifact with rollback, not a
  live edit to a running system. Declarative blueprint generation and image
  composing are maintained in the companion
  [`osbuild`](https://gitlab.com/syncopatedX/osbuild) repository.
- **Ansible — the system above the floor (Layer 1).** Host-level packages (`base_packages`),
  system services, hardware acceleration, system utilities and coding agent CLIs ([`roles/tools`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/tools)), and system-wide Flatpaks
  ([`roles/desktop`](file:///home/b08x/WorkspaceV3/Syncopated/workstation/roles/desktop)). Idempotent by contract —
  re-running a playbook against a converged host should report zero changes.

- **yadm — the user (Layer 2).** Dotfiles, shell environment (`~/.zshrc`), user version managers
  (`rbenv`, `rustup`), default Ruby gems, user Cargo crates, and user-space Flatpaks
  (`80-install-user-flatpaks.sh`). The one layer a re-image does not erase, and therefore the one
  layer where drift is permitted — under version control, where a change is recoverable and
  attributable.
- **Containers — the fast layer.** Everything that legitimately churns —
  language models, agent harnesses, RAG pipelines, tokenizers — runs inside
  its own dependency closure and never touches the host ABI. Dedicated containerized
  service stacks (Dify, Langfuse, Hermes, Ollama) and remediation tooling are
  managed in the companion [`llmops`](https://gitlab.com/syncopatedX/llmops) repository,
  free to be reckless precisely because the ground underneath them is not.

### Software arrival, in three tiers

One source of truth for how software arrives:

- **OS packages** — dnf, pacman, apt. Their versions are the distribution's
  problem; that is the service being bought.
- **Language ecosystems** — npm, uv, cargo, gem. An explicit version
  decision: pin to the system toolchain, or bring a newer one into user
  space. Both are fine. Half of each is not.
- **OSS projects** — git clones and release tarballs, pinned by revision or
  checksum, never by hope.

The practice is deciding what belongs on which layer — and then holding the
line when the next shiny thing arrives and demands to be installed directly
onto the host.

### Loops

Three pieces of tooling close a loop around the fleet. Every point where the
loop _acts_ is gated by a human:

- **Observe — `llm_analyzer` and `rich-ci-formatter`.** Two result callbacks,
  two audiences: one explains the run to a model and records it to the trace
  store; one explains the run to the human at the terminal. Agents drift
  without grounding; humans do too. The trace is the grounding for the
  machine; the rendered log, for you.
- **Remediate — `llmops/playbooks/remediate.yml`.** Operating from the companion
  [`llmops`](https://gitlab.com/syncopatedX/llmops) repository, the remediation
  pipeline reads a failing host's state across the fleet, asks a model for a
  diagnosis and a draft playbook, checks the draft mechanically — guards reject
  a draft that removes a volume, or replaces a working container without proving
  its replacement first — and executes nothing without an explicit `yes`. Confirmed
  fixes are indexed as reference for the next similar failure on any host.
- **Learn — `scripts/llm_trainset.py`.** Turns the accumulated traces into a
  DSPy trainset and scores it without running a playbook.

Agents provision the machines that watch agents provision machines. The loop
is permitted to exist because the layer beneath it does not move.

If you came for the workstation plumbing, read straight down. The intent
above is only the reason the plumbing looks like this.

## Lineage

This repository is not the first body this exercise has worn. The archive
began on the pragmatic ground, wandered upstream, and returned — the workload
changing underneath it as it went:

- **Before the archive — the disks in the closet.** Linux was not an early
  influence; it was not even an awareness — nothing in the house, the school,
  or the years after suggested it existed. Somebody once handed me a set of
  Red Hat 5 install disks; I said thanks, put them in a closet, and felt
  nothing, which was the correct amount of interest for a burden arriving
  without a reason to carry it. The actual entry was a pivot in the early
  thirties, on Fedora 10 — a chore to learn, though one spared the
  pre-installer horror stories — and five more years passed before Arch
  looked like a reasonable idea, which is the sentence that tells you the
  pivot took.
- **Orbitz — the vSphere years (before Nashville).** Configuration
  management in a different dialect: regional clusters inside a vSphere
  ecosystem behind a global travel website — five to ten thousand virtual
  machines, load balancing, caching, every moving part requiring its
  particular care — all of it managed with Chef and versioned in SVN. Chef
  made the concepts relatable, even comfortable in a metaphorical way; its
  syntax was still stereo instructions, which is a style preference and is
  admitted as such. SVN was SVN. The standing thought experiment — that
  estate re-run under Ansible — dates from here. The same years paid a second, quieter discipline:
  hand-trimmed kickstarts — images made as bare as they could be without
  sacrificing what the application on top needed — so that load moved not by
  updating a running estate but by re-imaging machines in seconds; the habit
  that the companion
  [`osbuild`](https://gitlab.com/syncopatedX/osbuild) repository would
  eventually make its whole subject.
- **Nashville (2014–2015)** — a client's Azure-hosted CI/CD pipeline on
  CentOS 7:
  Jenkins, GitLab, MariaDB with GTID, Nginx, Redis, HAProxy, CIS hardening,
  three environments, twenty-one roles. The infrastructure belonged to the
  client — their Azure instance, engineered and managed from this side while
  their team developed on it. The thesis was already whole in the notes from
  back then: no one should ever have to log into these hosts — every change
  flows through Ansible.
- **Columbus (2016)** — the break. Several years of high-stress DevOps work,
  then a deliberate exit and a turn to the Linux audio ecosystem — JACK,
  realtime privileges, low-latency tuning. The experimental role collection
  that follows grew out of this period.
- **ArchLabs** — the upstream excursion: a complete Arch playbook with a
  dedicated realtime-audio role, hosts managing themselves with
  `ansible-pull`. `soundbot` enters the inventory here and has never left.
- **pop!\_OS** — the middle ground, tried and found to be someone else's
  philosophy.
- **Fedora (Ansible_RAG)** — the archive itself: every Ansible tree from
  those years, parsed into 1,400+ task files across 68 module buckets — the
  raw material for deciding which patterns become a retrievable corpus and
  which get discarded.

The workload changed — enterprise CI/CD first, realtime audio after — but the
tension underneath did not, and the two workloads enforced opposite poles of
it. The Nashville pipeline is the immutability pole: cattle, hardened, no
human hands on the machines. The audio workstation is the other pole: an
instrument, hand-tuned mid-session, where re-rendering the machine from a
declaration is the last thing anyone wants. Attempts to declare all of it
fight the user; attempts to declare none of it lose the machine. Those are
also, not coincidentally, the two populations any studio-scale pipeline has
to keep alive at once.

The layer split is the settled compromise: make immutable what can be
immutable, manage what belongs to the system, and let the rest drift — under
version control, where a change is recoverable and attributable. Drift with
a changelog beats drift without one, and it beats enforced stasis too.

## The Next Entries

The practice changed stakes in the past three or four years, and the change
arrived with the generative tooling: the old inclination toward design
patterns — infrastructure as code, as a philosophy, a methodology — was
redirected and reinvigorated, though not in the same direction. The exercise
was a painting class; it has become a sporting event. Both require skill and
experience. One comes with less pressure. The other comes with considerably
more interest and more fun. Which is which on a given week is a set of
barometer readings not to be ignored.

So the repository sits in an in-between state, and the in-between state is
the honest description of a practice rather than a product. The next entries
on the list:

- **Ansible modules in Ruby.** No specific use case is in my head at the
  moment — a sentence recorded with historic dignity — but the use case, when
  it arrives, will most likely be something that applies pragmatically to an
  enterprise. The word here includes small businesses; an enterprise, not a —
  well, anyhow.
- **A blueprint corpus.** The cleanest modules and tasks I can write or
  collect, compiled into a dataset — the purpose the `Ansible_RAG` material
  was always pointing at, with its 1,400+ parsed task files waiting to be
  decided upon.
- **A generation interface.** The corpus as a backend of templates, reached
  through an API or an MCP call, so that specifying a playbook in plain text
  — a request, a prompt, a statement, an instruction — produces the playbook
  assembled from the blueprints.

Which is a retrieval-augmented generation pipeline refined for exactly this
material — which, I assume, is what IBM and Red Hat spend most of their time
doing.
