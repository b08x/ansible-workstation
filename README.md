<div align="center">

# Syncopated Workstation

A deliberately boring foundation under a fast-moving ecosystem.

Ansible control repository for provisioning Fedora and AlmaLinux development
workstations — desktop, virtualisation, container runtimes, and a local LLM ops
stack — from a single inventory.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![CI](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml/badge.svg)](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml)

</div>

## Preface

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
to fighting the shifting sands underneath.

Then the LLM ecosystem moved the spotlight onto exactly this choice. When the
application layer stops executing predictable, hard-coded logic and starts
running non-deterministic prompts, autonomous agent loops, and dynamic tool
calls, the host operating system can no longer afford to be a moving target. A
multi-agent system orchestrates file parsers, Python runtimes, and external
APIs; if the base OS changes behavior under it during a routine update,
debugging a rogue tool call becomes archaeology. Specialized compute is
fragile enough on its own — CUDA toolkits and GPU drivers against kernel
namespaces — without the floor moving too.

So this repository runs at two speeds.

The **slow layer** is deliberately boring: idempotent roles, explicit variable
tiers, distributions asserted before anything touches the disk, firewall
rules co-located with the services that need them. Ansible's whole job here is
to keep this layer honest — a 2:00 AM automated update should be a non-event.

The **fast layer** is everything that legitimately churns: language models,
agent harnesses, RAG pipelines, tokenizers, the tooling that reinvents itself
weekly. That layer lives in containers and disposable images, walled off from
the host's ABI, free to be reckless precisely because the ground underneath it
is not.

Make yourself comfortable. The plumbing below is just the argument, load-bearing.

## Why This Exists

Practically: this repository renders the workstations and servers in its
inventory from a single declaration. But the machines are the current
instantiation, not the point. The repository is an archive of blueprints —
methods, patterns, known-good configurations — that can be picked up and
pointed at any host list, not only mine.

Declaration is split across three layers, each with exactly one owner:

- **The image** (osbuild, bootc) — the floor: kernel, drivers, the base
  package set. Built, never mutated in place. A change is a new artifact with
  rollback, not a live edit to a running system.
- **Ansible** — system state above the floor: repositories, services, container
  runtimes, system-wide capability toggles.
- **yadm** — the user: dotfiles, shell, per-user paths. The one layer a
  re-image does not erase.

And one source of truth for how software arrives, in three tiers:

- **OS packages** — dnf, pacman, apt. Their versions are the distribution's
  problem; that is the service being bought.
- **Language ecosystems** — npm, uv, cargo, gem. These carry an explicit
  version decision: pin to the system toolchain, or install a newer toolchain
  in user space. A bleeding-edge crate on AlmaLinux 10.2 with its system Rust
  either gets pinned to what the base supports, or brings its own Rust into
  `~/.local`. Both are fine. Half of each is not. The same contract holds for
  Go, and for every toolchain that moves faster than the base.
- **OSS projects** — git clones and release tarballs, pinned by revision or
  checksum, never by hope.

The practice is deciding what belongs on which layer — and then holding the
line when the next shiny thing arrives and demands to be installed directly
onto the host.

Three loops still intertwine, each re-grounded in that decision:

- **Configuration management as anchoring.** Every role is written to be
  re-runnable: idempotent tasks, explicit variable tiers, firewall rules
  co-located with their services. Agents drift without grounding; humans do
  too. These conventions are the grounding.
- **Technical debt bankruptcy, one layer down.** The repository was restructured
  wholesale into a monolith — roles pulled natively into `roles/`, git
  submodules severed — because a fragmented control plane is its own kind of
  moving target. The base layer's management should be as boring as the base.
- **Agentic self-reference.** The `llm_analyzer` callback and its append-only
  JSONL trace store record what models actually do against real playbooks, and
  `scripts/llm_trainset.py` turns those traces into DSPy trainsets. Agents
  provision the machines that watch agents provision machines. The loop is
  permitted to exist because the layer beneath it does not move.

If you came for the workstation plumbing, read straight down. The philosophy
is only the reason the plumbing looks like this.

## Lineage

This repository is not the first body this exercise has worn. The archive
began on the pragmatic ground, wandered upstream, and returned — the workload
changing underneath it as it went:

- **fortyau (2014–2015)** — the origin: a Nashville startup's CI/CD pipeline on
  CentOS 7. Twenty-one roles — Jenkins, GitLab, MariaDB master-slave with GTID,
  Nginx, Redis, Graylog, HAProxy, CIS hardening, Azure provisioning, three
  environments. The thesis is already whole in the notes from back then: no
  one should ever have to log into these hosts — every change flows through
  Ansible. The pragmatist ground was the starting point, not the destination.
- **ArchLabs** — the upstream excursion. A complete Arch playbook with a dedicated
  audio role: JACK, PulseAudio, or PipeWire selection, realtime privileges,
  low-latency kernel and CPU tuning, archaudio and chaotic-aur repositories,
  hosts managing themselves through `ansible-pull`. `soundbot` enters the
  inventory here and has never left it.
- **pop!_OS** — the middle ground, visited. A collection scaffolded and barely
  begun; mostly evidence that the middle ground was tried and found to be
  someone else's philosophy.
- **Fedora (Ansible_RAG)** — not a working collection but an archive: an rsync of
  every Ansible tree from those years, duplicate role generations and all. The
  `Ansible_RAG_Tasks` parse — 1,400+ task files across 68 module buckets — and
  the `archive_tools` pipeline (extract, dedupe, merge, embed) are the first
  pass at deciding which of those years of patterns become a retrievable corpus,
  and which get discarded.

The workload changed — enterprise CI/CD first, realtime audio programming and
production after — but the tension underneath did not, and the two workloads
enforced opposite poles of it. fortyau is the immutability pole: cattle,
hardened, no human hands on the machines. The audio workstation is the other
pole. An artist's workstation is an instrument. It accumulates studio session
configurations, custom patches,
plugin collections, hand-tuned realtime settings, all of it edited live by the
person mid-session, when re-rendering the machine from a declaration is the
last thing anyone wants. Attempts to declare all of it fight the user. Attempts
to declare none of it lose the machine.

The layer split above is the settled compromise, learned across those years:
make immutable what can be immutable (the image), manage what belongs to the
system (Ansible), and let the rest drift — but drift under version control, in
the yadm layer, where a change is at least recoverable and attributable. Drift
with a changelog beats drift without one, and it beats enforced stasis too.

## Iterations

The repository has been through several configuration-management iterations,
and it is entering another: a retooling pass that treats the workstation itself
as the test bed for the two-speed split described above.

What broke on the bare-metal path was predictable in hindsight. Agent tooling
churns on a weekly cadence that a dnf-managed host was never meant to absorb.
Shared Python runtimes collide; a GPU driver update lands mid-pipeline and the compute layer
changes behavior underneath a non-deterministic application stack with no
rollback and no way to bisect. None of it is a *bug* in the old approach. It is
the old approach being asked to carry a load its philosophy was never aligned
for.

The agent layer turned out to resemble distro hopping more than a trust
problem. The baseline functionality — edit tasks, run linters, draft roles —
exists in all of them: antigravity-cli, claude-code, claude-desktop,
hermes-agent, mistral-vibe, opencode. What differs is the quirks and niches:
how each one handles context, tooling, and session state, and what each one
believes work should look like. The last couple of years have been less about
picking a winner than about surveying a field that reinvents itself weekly —
exploration, experimentation, tracking, monitoring, observing, iterating. The
`llm_analyzer` trace store is the other half of that apparatus: the agents are
observed while they work, the same way the hosts are. Most of these tools will
not be wanted a year from now, and that is fine — the point of a survey is
knowing what to keep. The `coding_agents` role became its own provisioning loop
for the same reason: the surveying is the workload, so it gets managed like
one.

What the container and atomic targets bought that bare metal could not:

- **Rollback.** A bootc/atomic host is an image transaction — failed retool is
  a reboot into the previous deployment, not a weekend of manual repair.
- **Reproducibility.** The base image is built by `osbuild` from declarative
  inputs, so "which host am I on" has a checksum for an answer.
- **Isolation of the churn.** Cutting-edge Python data pipelines, tokenizers,
  and experimental LLM harnesses run inside container sandboxes with their own
  dependency closure. The host's ABI stays untouched while the layer above it
  reinvents itself.

The traditional dnf path is retained, not deprecated: it remains the boring
baseline the split is anchored to, and the path the pre-bootc hosts still walk.

## Installation

The control node needs `ansible-core` 2.15 or newer and Python 3.9+. Managed
hosts need SSH and a `dnf`-based distribution; several roles assume Fedora or
AlmaLinux specifically and assert as much before doing damage.

<details>
<summary><b>Bootstrap script (recommended)</b></summary>

`bin/setup` is a robust TUI orchestrator powered by Gum that prepares a bare Fedora install to act as its own control node. It checks prerequisites, optionally runs Ansible system provisioning, and handles user dotfiles via yadm. Ensure you run this script as your normal user; it will prompt for sudo when needed.

```bash
git clone https://github.com/b08x/ansible-playbooks-workstation.git
cd ansible-playbooks-workstation
./bin/setup
```

The script is driven through a TUI; it gracefully handles interrupts and command failures, prompting rather than aborting.

</details>

<details>
<summary><b>Existing Ansible install</b></summary>

```bash
git clone https://github.com/b08x/ansible-playbooks-workstation.git
cd ansible-playbooks-workstation
```

Roles are located natively in the `roles/` directory, following a monolithic architecture. All playbooks will resolve roles natively without needing extra collections initialization.

</details>

<details>
<summary><b>Container — devcontainer</b></summary>

Definitions for both runtimes ship in `.devcontainer/`:

```bash
# Docker
devcontainer up --workspace-folder . --config .devcontainer/docker/devcontainer.json

# Podman
devcontainer up --workspace-folder . --config .devcontainer/podman/devcontainer.json
```

</details>

<details>
<summary><b>Disposable target — Vagrant</b></summary>

A `Vagrantfile` at the repo root provides a throwaway target for testing plays
that would otherwise need a spare machine.

```bash
vagrant up
```

> **Note:** On a host running both Docker and libvirt, Docker's `FORWARD DROP`
> policy supersedes libvirt's nftables accepts and silently strips outbound NAT
> from `virbr+` interfaces. The symptom is a guest that hangs forever on `dnf
> update` with no error. Allow the bridges explicitly:
>
> ```bash
> sudo iptables -I DOCKER-USER -i virbr+ -j ACCEPT
> sudo iptables -I DOCKER-USER -o virbr+ -j ACCEPT
> ```

</details>

## Usage

```bash
# System provisioning
ansible-playbook playbooks/base.yml

# One subsystem
ansible-playbook playbooks/desktop.yml

# Build a custom image
ansible-playbook playbooks/osbuild.yml

# Standalone service deployments
ansible-playbook playbooks/dify-docker.yml
ansible-playbook playbooks/langfuse-podman.yml

# Single role against any host in the group
ansible-playbook playbooks/tuning.yml --limit builder
```

### Playbooks

Playbooks that target the `workstations` group can run any single role
independently — each carries the full variable surface from `group_vars` and
role defaults, so overrides are always explicit.

**Development Workstation Roles**

Privileged playbooks (run with `become: true`):

| Playbook | Role | Tags |
| ---------- | ------ | ------ |
| `playbooks/base.yml` | base | base, system |
| `playbooks/tuning.yml` | tuning | tuning, system |
| `playbooks/desktop.yml` | desktop | desktop, system |
| `playbooks/libvirt.yml` | libvirt | libvirt, virt |
| `playbooks/containerd.yml` | containerd | containerd, virt |
| `playbooks/networking.yml` | networking | networking, system |

Unprivileged playbooks (run without `become`):

| Playbook | Role | Tags |
|----------|------|------|
| `playbooks/user.yml` | user | user, system |
| `playbooks/coding_agents.yml` | coding_agents | coding_agents, system |

**LLM Ops Roles**

The fast layer, deployed onto the boring base. Where a runtime is listed, the
service runs containerized rather than on the host directly.

| Playbook | Role | Host | Runtime |
| ---------- | ------ | ------ | --------- |
| `playbooks/dify-docker.yml` | dify | ninjabot | Docker |
| `playbooks/langfuse-podman.yml` | langfuse | tinybot | Podman |
| `playbooks/ollama.yml` | ollama | workstations | — |
| `playbooks/hermes.yml` | hermes | workstations | — |
| `playbooks/tts.yml` | tts | workstations | — |
| `playbooks/remediate.yml` | remediation plugins ([docs](plugins/action/README.md)) | `-e target=<host>` | Podman |

**RHEL Builder Roles**

| Playbook | Role | Host |
| ---------- | ------ | ------ |
| `playbooks/osbuild.yml` | osbuild | osbuild_targets |
| `playbooks/composer_cli.yml` | composer_cli | builder |
| `playbooks/rpm_dev.yml` | rpm_dev | builder |

**Storage Services**

| Playbook | Role | Tags |
| ---------- | ------ | ------ |
| `playbooks/nas.yml` | nas | nas |

**Standalone deployments** (role defaults, can be overridden with `-e`)

| Playbook | Role | Host | Runtime |
|----------|------|------|---------|
| `playbooks/dify-docker.yml` | dify | ninjabot | Docker |
| `playbooks/langfuse-podman.yml` | langfuse | tinybot | Podman |

`dify.yml` and `langfuse.yml` (without `-docker`/`-podman` suffix) are the plain
role playbooks targeting the `workstations` group; the suffixed variants target
the dedicated `dify` and `langfuse` inventory groups with service-specific defaults.

### Tags

Tags compose, so `--tags "virt"` covers libvirt and containerd together while
`--tags "libvirt"` narrows to one. The broadest are `system` — base, tuning,
desktop, user and coding_agents — and `virt`.

**System scope**

- `base`: Package baseline, repositories, system configuration.
- `tuning`: Kernel and scheduler tuning.
- `desktop`: Desktop environment and graphical applications, including VS Code and the Antigravity Hub/IDE.
- `sudoers`: `requiretty` handling, required for pipelining on non-RHEL distros.

**Virtualisation scope**

- `libvirt`: libvirt, KVM, and virtual networking.
- `containerd`: Container runtime.
- `virt`: Both of the above.

**User scope**

- `user`: Shell, dotfiles, per-user paths.
- `coding_agents`: Agent tooling — antigravity CLI, claude, crush, opencode, vibe, skills.

### Examples

```bash
# Target one host
ansible-playbook playbooks/base.yml --limit tinybot

# One subsystem
ansible-playbook playbooks/desktop.yml

# Standalone service deployments
ansible-playbook playbooks/dify-docker.yml
ansible-playbook playbooks/langfuse-podman.yml

# Dry run with diffs
ansible-playbook playbooks/base.yml --check --diff

# Virtualisation stack on the builder hosts
ansible-playbook playbooks/containerd.yml --limit builder

# Lint all roles
ansible-lint
```

## Configuration

Inventory lives in `inventory/hosts.ini`. Groups are arranged so membership is
declared once and reused: `workstations` collects `dev`, `builder`, `virt`,
`langfuse`, and `dify`; `osbuild_targets` is a children-group of `builder` rather
than a second copy of the same host list.

```ini
[workstations:children]
dev
builder
virt
langfuse
dify

[osbuild_targets:children]
builder
```

Variables resolve in the usual order — role defaults, then `group_vars/`, then
`host_vars/`, then extra vars. Naming follows two tiers, and the distinction is
load-bearing rather than cosmetic:

- **Host and domain scope** — semantic, unprefixed names such as `user.*`,
  `use_kvm` or `enable_third_party_repos`, describing hardware, primary user
  identity, or system-wide capability. Forcing role prefixes onto these distorts
  their meaning and duplicates them across roles, which is why
  `var-naming[no-role-prefix]` is skipped deliberately in `.ansible-lint`.
- **Role scope** — anything in a role's `defaults/`, `vars/`, or a `set_fact`
  carries a `<role>_` prefix. Registered variables carry one too, since `register`
  produces host-scoped names that collide across roles otherwise.

`ansible.cfg` enables JSON fact caching under `/tmp/ansible_cache`, SSH
pipelining, and the `llm_analyzer` callback. Logs land in `/tmp/ansible.log`.

## LLM Analyzer

A notification callback that sends each play and task to a model and records the
result. Analysis runs on a bounded worker pool, which is the point: Ansible calls
`v2_playbook_on_task_start` on its main thread and blocks until it returns, so a
synchronous analyzer adds a full round trip to every task in the playbook.

```ini
[defaults]
callbacks_enabled = llm_analyzer

[callback_llm_analyzer]
provider = openrouter
model = openrouter/deepseek/deepseek-v4-flash
temperature = 0.4
max_tokens = 8192
```

Six providers are supported — OpenAI, Gemini, Groq, OpenRouter, Cohere and
Anthropic — each reading its own `*_API_KEY` variable. Failed key validation
disables the callback and lets the playbook continue rather than failing the run.

Output lands in `llm_analysis/`: rendered Markdown per subject, and an
append-only JSONL trace store queried with DuckDB. `scripts/llm_trainset.py`
turns those traces into a DSPy trainset and scores it without running a playbook.

```bash
python scripts/llm_trainset.py stats
python scripts/llm_trainset.py evaluate
```

> **📖 Full documentation:** [`plugins/callback/README.md`](plugins/callback/README.md)
> covers every option, the trace layout, and the two settings whose names
> mislead — `max_tokens` caps output rather than context, and `async_workers = 0`
> is a correctness-neutral but very expensive default to choose.

## Image Building

The `rhel_builder` roles wrap the unified `image-builder` CLI and osbuild.
Targets are Fedora and AlmaLinux; the playbook asserts the distribution up front
so an unsupported host fails immediately rather than midway through a compose.

This is the machinery of the slow layer: the base image becomes a declarative
artifact — the same predictability the Enterprise Pragmatists sell, built
locally instead of subscribed to. A bootc build produces an atomic host where
updates and rollbacks are image transactions.

```bash
ansible-playbook playbooks/osbuild.yml
ansible-playbook playbooks/osbuild.yml -e "osbuild_build_bootc=true"
ansible-playbook playbooks/osbuild.yml -e "osbuild_only_generate=true"
```

`osbuild_distro` derives from the target's own facts, resolving to
`fedora-<version>` or `almalinux-<version>` unless overridden.

## Playbook Graphs

Rendered structure for each playbook lives in `docs/graphs/`, produced by
[ansible-playbook-grapher](https://github.com/haidaraM/ansible-playbook-grapher).
Both JSON and SVG are committed — the JSON retains the play/role/task hierarchy
as data, while the SVG is a finished graphviz layout that has already flattened
it into coordinates.

`site.json` is the one worth reaching for: it is the only graph covering both
plays, and therefore the only artifact showing the full provisioning shape. See
[`docs/graphs/README.md`](docs/graphs/README.md) for regeneration commands.

## Testing

```bash
# Lint natively
ansible-lint

# Molecule scenario
molecule test

# Python tests, parallel
pytest -vvv -n 2
```

The root `pre-commit` config runs black, isort, flake8, prettier, and ansible-lint
across the monolithic repository. Run `pre-commit run --all-files` from the repository root
to validate all roles and playbooks.

## Contributing

Issues and pull requests are welcome. The same constraints that shape the
repository shape contributions: idempotent tasks, the documented variable
tiers, and the layering rule — host-layer changes must be boring, and anything
that churns belongs in a container, not on the base. Roles follow the standard
layout natively in the repository, with distribution-specific tasks under
`tasks/distro/{{ ansible_distribution }}.yml`, and firewall rules co-located in
the role that opens the port rather than centralised — services stay
self-contained that way.

## License

GNU General Public License v3.0 or later.
