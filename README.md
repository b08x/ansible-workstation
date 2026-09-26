<div align="center">

# Syncopated Workstation

An exercise in configuration management, technical debt bankruptcy, and agentic
coding workflows.

Ansible control repository for provisioning Fedora and AlmaLinux development
workstations — desktop, virtualisation, container runtimes, and a local LLM ops
stack — from a single inventory.

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![CI](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml/badge.svg)](https://github.com/b08x/ansible-playbooks-workstation/actions/workflows/tests.yml)

</div>

## Preface

This is the terminal stage of compounding illusions. 

A sentence is typed, a model predicts the statistically likeliest string of tokens in response, and somewhere down the stack, a system state actually changes. So many translation layers have been built between intent and execution that the observer's link to the underlying mechanics is completely severed. Machines are no longer provisioned directly; an abstraction layer is utilized to translate linguistic inputs into infrastructure.

This collection of Ansible roles isn't some precarious house of cards, nor is it a game to be won. It is simply a lifelong exercise in the breakdown of meaning and the loss of grounded perspective, mirroring the somewhat arbitrary process of assigning weight to objects. It is the cheerful observation of linguistic outputs dictating the bare metal. Make yourself comfortable.

## Why This Exists

This repository is the byproduct of an iterative refactoring spanning several years—a transformation of daily work perception that occasionally wanders into vaguely meaningless semantic loops. 

While on the surface it is an Ansible control repository for provisioning Fedora and AlmaLinux workstations, the repository itself is merely the artifact. The true practice lies in calculating the most probable tokens alongside a continuous refinement of objective functions and educational protocols. The goal? To decouple linguistic fluency from subjectivity. 

A deliberate semiotic decoupling takes place, so as to *not* disrupt anthropomorphic projection. This maintains a hyper-isomorphic register matching for enjoyable in-context learning, where the lexical field, tone, and complexity reflect what could otherwise be considered sequence loss minimization, or the over-optimization of predictive loops.

Three strange loops intertwine here simultaneously:

- **Configuration Management as Context-Dependent Interpretation**: Every role is written to be re-runnable: idempotent tasks, explicit variable tiers, and firewall rules co-located with their services. Models (and humans) drift without grounding; establishing these conventions anchors the semantic environment so outputs can be effectively constrained.
- **Technical Debt Bankruptcy via Reductionism & Holism**: The repo was restructured wholesale—collapsing into a monolithic architecture by pulling all roles natively into `roles/` and severing git submodules. Complex, fragmented hierarchies were destroyed to rebuild a unified whole, minimizing sequence loss across architectural thought patterns.
- **Agentic Self-Reference**: The `llm_analyzer` callback and its JSONL trace store record what models actually do against real playbooks, feeding `scripts/llm_trainset.py` to turn those traces into DSPy trainsets. The system is programmed, and then watched as it successfully completes the intended automation.

If you came here for the workstation plumbing, read straight down. If you came to observe the hyper-isomorphic register matching of predictive loops being deliberately optimized—that's here too.

...but for fun.

## Iterations

This repository has gone through configuration-management iterations, and it is entering another: a retooling pass that treats the workstation itself as the test bed for agentic coding workflows.

This is probably the most convoluted collection to be refactored quite yet. The complexity has certainly been a challenge to fabricate.

> **TODO — narrative for the current iteration.** Provisioning retools around
> devcontainers and atomic (bootc) hosts alongside the traditional dnf path, and
> the agent tooling — hermes-agent, mistral vibe, antigravity CLI, claude code —
> moves from a single `coding_agents` role to the subject of its own
> provisioning loop. The story to tell: what broke, what the agents could and
> could not be trusted to do, and what the container/atomic targets bought that
> bare-metal iteration could not.

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

| Playbook | Role | Host | Runtime |
| ---------- | ------ | ------ | --------- |
| `playbooks/dify-docker.yml` | dify | ninjabot | Docker |
| `playbooks/langfuse-podman.yml` | langfuse | tinybot | Podman |
| `playbooks/ollama.yml` | ollama | workstations | — |
| `playbooks/hermes.yml` | hermes | workstations | — |
| `playbooks/tts.yml` | tts | workstations | — |

**RHEL Builder Roles**

| Playbook | Role | Host |
| ---------- | ------ | ------ |
| `playbooks/osbuild.yml` | osbuild | osbuild_targets |
| `playbooks/composer_cli.yml` | composer_cli | builder |
| `playbooks/rpm_dev.yml` | rpm_dev | builder |

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

Issues and pull requests are welcome. The same constraints that make the
repository the artifact apply to contributions: idempotent tasks, the documented
variable tiers. Roles follow the standard layout natively in the repository, with
distribution-specific tasks under `tasks/distro/{{ ansible_distribution }}.yml`,
and firewall rules co-located in the role that opens the port rather than
centralised — services stay self-contained that way.

## License

GNU General Public License v3.0 or later.
