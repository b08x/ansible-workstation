<div align="center">

# Ansible for a Workstation

A deliberately boring foundation under a fast-moving ecosystem.

Ansible control repository for provisioning Fedora and AlmaLinux machines —
system configuration, virtualisation, container runtimes, custom image
builds, and a local LLM ops stack — from a single inventory.

Kept as a working notebook: the roles, playbooks, and plugins are the current
entries of a decade's experiments, and the git history keeps the earlier
entries.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15-black.svg)](https://docs.ansible.com/ansible-core/devel/)
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
AlmaLinux base moves on a ten-year clock, Fedora on a thirteen-month one,
Ansible whenever a playbook runs, the agent tooling on whatever upstream
shipped this week. Syncopated is the practice of letting those disparate
systems land on their own offbeats without losing the downbeat underneath
them.

Make yourself comfortable. The plumbing below is just the argument,
load-bearing.

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

- **Image builds run on all three targets.** The `osbuild` role composes
  Fedora, AlmaLinux, and Rocky Linux ISOs from declarative blueprints —
  Fedora and AlmaLinux through `playbooks/osbuild.yml`, Rocky through
  `playbooks/osbuild-rocky-iso.yml`. Repository GPG keys are fetched locally
  and verified before any compose; the target distribution is asserted
  before anything touches the host. The base image as a reproducible
  artifact instead of a live-edited system.
- **Full workstation provisioning runs on Fedora and AlmaLinux.** `site.yml`
  imports four plays — base, system, user, coding agents — against the
  `workstations` group, with roles living natively in `roles/` after a
  deliberate restructuring out of git submodules. Rocky Linux is a declared
  target and has not been walked yet.
- **The remediation pipeline works.** `playbooks/remediate.yml` reads a
  failing host, asks a model for a diagnosis and a draft playbook, checks
  the draft mechanically, and executes nothing without a typed `yes`. It
  runs against the real fleet and carries 159 pytest tests that need no
  network.
- **Standalone deployments work.** Langfuse deploys under Podman, Dify under
  Docker, each from its own playbook with service-specific defaults.
- **Observability runs in both directions.** The `llm_analyzer` callback
  records what every play and task actually does to an append-only trace
  store, and `scripts/llm_trainset.py` turns those traces into a scored DSPy
  trainset; `rich-ci-formatter` renders the same runs for the human at the
  terminal — DNF5 transaction tables, systemd transitions, phase banners.
  The formatter works; its failure path is the owed polish: a failed task
  currently obscures more than it shows.
- **Testing exists where the risk lives.** The `base` role carries a Molecule
  scenario that builds Fedora and AlmaLinux containers, converges twice, and
  fails on any second-run change. Everything lints.
- **bootc is direction, not state.** The image-transaction path is designed
  for, walked partway; the dnf baseline carries the weight today.

What is owed is polish, not function: idempotency lock-tightness on re-runs,
the `rich-ci-formatter` failure path, and a recorded end-to-end demonstration.
The evidence so far is convergence on real hosts and the trace store, not a
screencast.

## Intent

One decision, applied consistently, is the whole architecture: the base does
not move, so everything above it is allowed to. The intents are recorded
explicitly, layer by layer, because the parts only make sense as a whole.

### Layers

- **The image — the floor.** Kernel, drivers, the base package set. Built,
  never mutated in place; a change is a new artifact with rollback, not a
  live edit to a running system.
- **Ansible — the system above the floor.** Repositories, services, container
  runtimes, system-wide capability toggles. Idempotent by contract —
  re-running a playbook against a converged host should report zero changes —
  with explicit variable tiers and firewall rules co-located with the
  services that need them.
- **yadm — the user.** Dotfiles, shell, per-user paths. The one layer a
  re-image does not erase, and therefore the one layer where drift is
  permitted — under version control, where a change is recoverable and
  attributable.
- **Containers — the fast layer.** Everything that legitimately churns —
  language models, agent harnesses, RAG pipelines, tokenizers — runs inside
  its own dependency closure and never touches the host ABI. Free to be
  reckless precisely because the ground underneath it is not.

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
loop *acts* is gated by a human:

- **Observe — `llm_analyzer` and `rich-ci-formatter`.** Two result callbacks,
  two audiences: one explains the run to a model and records it to the trace
  store; one explains the run to the human at the terminal. Agents drift
  without grounding; humans do too. The trace is the grounding for the
  machine; the rendered log, for you.
- **Remediate — `playbooks/remediate.yml`.** Reads a failing host's state,
  asks a model for a diagnosis and a draft playbook, checks the draft
  mechanically — guards reject a draft that removes a volume, or replaces a
  working container without proving its replacement first — and executes
  nothing without an explicit `yes`. Confirmed fixes are indexed as
  reference for the next similar failure on any host.
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

- **Nashville (2014–2015)** — a startup's CI/CD pipeline on CentOS 7:
  Jenkins, GitLab, MariaDB with GTID, Nginx, Redis, HAProxy, CIS hardening,
  three environments, twenty-one roles. The thesis was already whole in the
  notes from back then: no one should ever have to log into these hosts —
  every change flows through Ansible.
- **Columbus (2016)** — the break. Several years of high-stress DevOps work,
  then a deliberate exit and a turn to the Linux audio ecosystem — JACK,
  realtime privileges, low-latency tuning. The experimental role collection
  that follows grew out of this period.
- **ArchLabs** — the upstream excursion: a complete Arch playbook with a
  dedicated realtime-audio role, hosts managing themselves with
  `ansible-pull`. `soundbot` enters the inventory here and has never left.
- **pop!_OS** — the middle ground, tried and found to be someone else's
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
