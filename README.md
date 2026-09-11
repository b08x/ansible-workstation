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

## Why This Exists

The repository itself is the artifact. The process of building it — forcing LLM
agents to respect Ansible idempotency rather than hallucinating bash scripts —
is the practice.

Three things are being worked out here simultaneously:

- **Configuration management as discipline.** Every role is written to be
  re-runnable: idempotent tasks, distribution asserts before damage, explicit
  variable tiers, and firewall rules co-located with the service that owns them.
  The conventions documented below exist because agents (and humans) drift
  without them.
- **Technical debt bankruptcy.** The repo was restructured wholesale — roles
  promoted into purpose-built collections, defaults/vars inversions fixed,
  dead handlers and ad-hoc shell migrations audited away — rather than
  incrementally patched. The sub-module layout makes that bankruptcy
  repeatable: each collection gets a clean history instead of inheriting the
  control repo's.
- **Agentic coding workflows.** The `llm_analyzer` callback and its JSONL
  trace store record what models actually do against real playbooks;
  `scripts/llm_trainset.py` turns those traces into DSPy trainsets. The
  playbooks, their committed graphs under `docs/graphs/`, and the lint and
  test surface are the guardrails that make agent-driven change safe.

If you came here for the workstation plumbing, read straight down. If you came
for the meta-practice, the LLM Analyzer and Playbook Graphs sections are the
interesting parts.

## Iterations

This repository has gone through configuration-management iterations, and it is
entering another: a retooling pass that treats the workstation itself as the
test bed for agentic coding workflows.

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
<summary><b>Fedora — bootstrap script (recommended)</b></summary>

`bootstrap.sh` prepares a bare Fedora install to act as its own control node. It
installs `ansible-core`, the `posix` and `utils` collections, build tooling,
`yadm` for dotfiles, and wires up Flathub. Root is required, since the whole
script is `dnf` work.

```bash
git clone --recurse-submodules https://github.com/b08x/ansible-playbooks-workstation.git
cd ansible-playbooks-workstation
sudo ./bootstrap.sh
```

The script installs [gum](https://github.com/charmbracelet/gum) first and drives
the rest of the run through it; interrupts and command failures both prompt
rather than abort, so a single failed `dnf` transaction does not discard the
whole session.

</details>

<details>
<summary><b>Existing Ansible install</b></summary>

```bash
git clone https://github.com/b08x/ansible-playbooks-workstation.git
cd ansible-playbooks-workstation
git submodule update --init --recursive
```

The submodule step is not optional. The collections live under
`collections/ansible_collections/b08x/` and every playbook resolves roles
through them; skipping it produces role-not-found errors rather than anything
that names the real cause.

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

**devworkstation collection**

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

**llmops collection**

| Playbook | Role | Host | Runtime |
| ---------- | ------ | ------ | --------- |
| `playbooks/dify-docker.yml` | dify | ninjabot | Docker |
| `playbooks/langfuse-podman.yml` | langfuse | tinybot | Podman |
| `playbooks/ollama.yml` | ollama | workstations | — |
| `playbooks/hermes.yml` | hermes | workstations | — |
| `playbooks/tts.yml` | tts | workstations | — |

**rhel_builder collection**

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

# Lint a collection
cd collections/ansible_collections/b08x/devworkstation && ansible-lint
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

The `rhel_builder` collection wraps the unified `image-builder` CLI and osbuild.
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
# Lint (from a collection directory)
ansible-lint

# Molecule scenario
molecule test

# Python tests, parallel
pytest -vvv -n 2
```

Two pre-commit configurations exist and they are not interchangeable. The root
config runs black, isort, flake8, prettier and ansible-lint; each collection
carries its own with a broader hook set that notably excludes ansible-lint. A
`pre-commit run --all-files` from the repository root does not apply collection
hooks, so collection work wants a run from inside the collection.

## Contributing

Issues and pull requests are welcome. The same constraints that make the
repository the artifact apply to contributions: idempotent tasks, the documented
variable tiers, and collection changes committed in their own repository before
the pointer bump here. Roles follow the standard layout, with
distribution-specific tasks under `tasks/distro/{{ ansible_distribution }}.yml`,
and firewall rules co-located in the role that opens the port rather than
centralised — services stay self-contained that way.

The collections are submodules: changes there are committed and pushed in the
collection repository first, then the pointer bump follows in this one.

## License

GNU General Public License v3.0 or later. Each collection carries the full text
in its own `LICENSE`.
