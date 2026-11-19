<div align="left">

# Ansible Collection: Development Workstation

An Ansible control repository provisioning Fedora 44 / AlmaLinux 10 / Rocky Linux 10
workstations across fourteen modular roles. Positioned as a deterministic execution engine,
validation gate, and controlled reference dataset within a multi-agent engineering workflow.
ansible-core >= 2.15 (verified 2.18–2.20), Python 3.12+ (3.14 aligned), x86_64, root required.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.15%20(verified%202.18--2.20)-black.svg)](https://docs.ansible.com/ansible-core/devel/)
[![python](https://img.shields.io/badge/python-3.14%20%7C%203.12%2B-blue.svg)](https://www.python.org/)
[![Fedora](https://img.shields.io/badge/Fedora-44-294172.svg)](https://fedoraproject.org/)
[![AlmaLinux](https://img.shields.io/badge/AlmaLinux-10-blue.svg)](https://almalinux.org/)
[![Rocky Linux](https://img.shields.io/badge/Rocky%20Linux-10-green.svg)](https://rockylinux.org/)
[![dnf5](https://img.shields.io/badge/dnf5-validated-blueviolet.svg)](https://github.com/rpm-software-management/dnf5)
[![molecule](https://img.shields.io/badge/molecule-tested-blue.svg)](https://github.com/ansible-community/molecule)
[![ansible-lint](https://img.shields.io/badge/ansible--lint-enforced-black.svg)](https://github.com/ansible/ansible-lint)
[![yadm](https://img.shields.io/badge/yadm-dotfiles-blue.svg)](https://yadm.io/)
[![libvirt](https://img.shields.io/badge/libvirt%2FKVM-enabled-red.svg)](https://libvirt.org/)
[![Vagrant](https://img.shields.io/badge/Vagrant-libvirt-1867F0.svg)](https://www.vagrantup.com/)
[![Scaffolding: Empirical](https://img.shields.io/badge/scaffolding-forged%20by%20failure-critical.svg)](#the-recursive-multi-agent-genesis-from-stochastic-generation-to-deterministic-scaffolding)

</div>

---

An Ansible control repository that converges a Fedora 44 / AlmaLinux 10 / Rocky Linux 10
x86_64 host into a fully configured developer workstation. The architecture reframes Ansible
from a traditional configuration tool into a **deterministic execution engine and validation gate**
in an agentic pipeline. While probabilistic natural language decoders generate intent, Ansible
enforces the deterministic contract: AST validation, precondition assertion gates, and verified
idempotency.

The machine is architected across decoupled functional layers:

- **NLUI & Gherkin Gate**: Natural Language User Interface sitting atop the stack, allowing users
  to express high-level feature sets. Step gates validate natural language requirements into
  structured Gherkin syntax (`Feature / Scenario / Given / When / Then`) before deterministic
  compilation into Ansible tasks and plays.
- **Layer 0 (osbuild)**: Base system composition. The immutable floor comes from companion
  [osbuild](https://gitlab.com/syncopatedX/osbuild) pipelines: the functional declarative **ISO installer pipeline**
  or the **bootc immutable container-image pipeline**.
- **Layer 1 (Ansible)**: This repository. Deterministic host orchestration, system services, daemon
  configuration, desktop environments, developer toolchains, and container engines across
  fourteen modular roles—idempotent by contract. Drives both running workstation convergence and
  offline image composition parity.
- **Layer 2 (yadm)**: User dotfiles, shell profiles, editor configurations, and GPG keys.
  Cloned at first login and owned exclusively by the user; preserved across OS re-imaging.
- **Fast Layer (Containers)**: Podman and containerd execution sandboxes for ephemeral and
  isolated developer environments.

Whether evaluating this stack as a systems architect, maintaining it as an operator, or
navigating it via an AI coding agent, this repository serves as a **controlled reference distilled dataset**
where autonomous agents can reference vetted patterns, domain-specific idioms, single-ownership rules,
and architectural invariants to generate tasks and playbooks on demand.

AI coding agents should review [AGENTS.md](AGENTS.md) as the authoritative invariant specification
before proposing modifications, and consult [The Map](#the-map) for role entry points. Evidence
sourcing and empirical uncertainty classifications are documented in
[docs/audit-notes.md](docs/audit-notes.md).

## Contents

- [The Recursive Multi-Agent Genesis: From Stochastic Generation to Deterministic Scaffolding](#the-recursive-multi-agent-genesis-from-stochastic-generation-to-deterministic-scaffolding)
- [Ansible as Deterministic Execution Gate & Validator](#ansible-as-deterministic-execution-gate--validator)
- [Natural Language User Interface (NLUI) & Gherkin-Gated Pipeline](#natural-language-user-interface-nlui--gherkin-gated-pipeline)
- [Converged Parity: Image Composition & Host Convergence](#converged-parity-image-composition--host-convergence)
- [Controlled Reference Distilled Dataset](#controlled-reference-distilled-dataset)
- [The Architecture and Decoupling Contract](#the-architecture-and-decoupling-contract)
- [Two Commands to Converge](#two-commands-to-converge)
- [Machine Lifecycle & Firstboot Architecture](#machine-lifecycle--firstboot-architecture)
- [Prospective Intent & Telemetry: The llm_analyzer Framework](#prospective-intent--telemetry-the-llm_analyzer-framework)
- [Improvement Cycles (PDCA)](#improvement-cycles-pdca)
- [Working on the Repository](#working-on-the-repository)
- [The Map](#the-map)
- [Where to Go from Here](#where-to-go-from-here)
- [License](#license)

---

## The Recursive Multi-Agent Genesis: From Stochastic Generation to Deterministic Scaffolding

Most infrastructure repositories present an idealized, static end-state. This repository is the
hardened scaffolding developed across a ten-month development arc (January 30 – November 5, 2026)
to reconcile probabilistic language model code generation with the deterministic runtime
invariants of the Linux kernel and systemd.

Its origin story is inherently recursive. In the maintainer's retrospective account:

> *"This project was generated by a multi-agent workflow that was generated by a different
> multi-agent workflow that was generated from sitting down one day and sort of just talking
> out what sort of automated tools I would personally find useful."*

Through guided context engineering across multiple agentic coding harnesses (OpenCode, Claude Code,
Antigravity, Charm Crush, and Mistral Vibe), models operated across vanilla configurations,
runtime-invoked skills, tailored persona designs, and multi-agent workflows. Within the local
code-insights analytics database (`~/.code-insights/data.db`), a heuristic query matching 46 project
lineage path patterns captures 512 recorded AI-assisted sessions (at a model-estimated token cost of
~$2,057.09), documenting instances where language model harnesses executed file mutations against
POSIX system state:

| Coding Tool / Harness | Sessions | Messages | Avg Msgs/Session | Est. Token Cost |
|:----------------------|:--------:|:--------:|:----------------:|:---------------:|
| opencode              | 221      | 4,212    | 19.1             | $3.53           |
| mistral-vibe          | 104      | 5,942    | 57.1             | $167.81         |
| claude-code           | 78       | 8,167    | 104.7            | $1,170.40       |
| antigravity           | 65       | 2,038    | 31.4             | $0.09           |
| gemini-cli            | 21       | 3,588    | 170.9            | $608.53         |
| crush                 | 20       | 192      | 9.6              | $0.51           |
| claude-desktop        | 3        | 628      | 209.3            | $106.22         |
| **Total Lineage**     | **512**  | **24,767** | **48.4**       | **~$2,057.09**  |

*(Note: Session metrics are queried via heuristic path and name LIKE patterns from `~/.code-insights/data.db`,
capturing instrumented AI-assisted sessions across 46 project lineage entries while omitting untracked tools
and direct manual commits, as documented in [docs/audit-notes.md](docs/audit-notes.md). Token costs are
model-based estimates rather than invoiced billing.)*

Statistical language models generate token sequences without runtime awareness or formal verification
of Linux kernel memory constraints, process hierarchies, or display server session state. When prompted
to tune swap, an agent generated tasks attempting to hot-reload zram while holding five gigabytes of
active swap, triggering a kernel `EBUSY` failure. During system memory configuration, two separate roles
(`base` and `tuning`) both templated `/etc/systemd/zram-generator.conf` with conflicting calculation
algorithms (`memtotal/2` vs `min(ram, 8192)`), repeatedly overwriting the destination file due to the
absence of a single-writer invariant. When managing display services, an automated handler executed an
unconditional `systemctl restart gdm`, immediately terminating the active Wayland seat session of the
supervising engineer.

Within the subset of 499 sessions analyzed for interaction friction in the code-insights corpus,
**53.1%** (265 sessions) recorded a mid-flight course correction where the operator intervened to redirect
execution trajectory. Rather than discarding generative workflows, recurring operational collisions—including
ungrounded configuration parameters, privilege boundary violations, and unreviewed version control
commits—were captured as empirical boundary tests. The maintainer cataloged **22 distinct empirical failure
points** (detailed in [`docs/failure-points.md`](docs/failure-points.md)), translating operational friction
into deterministic architectural invariants:

1. **The Live Swap Reconfiguration (Failure Point 1)**: An agent issued `systemctl restart systemd-zram-setup@zram0`
   while holding 5 GiB of active swap. The kernel rejected writes to `/sys/block/zram0/comp_algorithm`,
   and swapoff failed with `EBUSY`. *Remedy*: In `roles/tuning/tasks/zram.yml`, kernel memory
   reconfiguration is staged to disk, systemd is reloaded (`notify: Reload systemd`), and device
   reactivation is deferred strictly to system reboot.
2. **The Dual-Role Configuration Collision (Failure Point 2)**: Both `base` and `tuning` templated
   `/etc/systemd/zram-generator.conf` with conflicting calculation algorithms (`memtotal/2` vs `min(ram, 8192)`).
   *Remedy*: Strict Single File Ownership (`docs/conventions.md:57-63`). Duplicate tasks were purged;
   `roles/tuning` is the sole authorized writer.
3. **The Unwired Compiler Probe (Failure Point 3)**: A capability probe verified `/opt/intel/oneapi/compiler/latest/bin/icx`,
   set `backend=sycl`, but failed to pass `-DCMAKE_CXX_COMPILER` or source `setvars.sh` in the build environment—silently
   compiling with default GNU gcc. *Remedy*: Probes must execute functional usability checks (`--version`) and
   wire detection results directly into consumer variables.
4. **Display Manager Session Termination (Failure Point 4)**: A handler triggered an unconditional restart
   of `gdm.service`, killing the active Wayland session of the engineer monitoring convergence. *Remedy*:
   Seat-filtered session detection via `loginctl list-sessions` in `roles/gnome/handlers/main.yml` and `roles/cosmic/handlers/main.yml`. Display
   manager restarts are inhibited if local seat sessions exist (`_<role>_dm_seat_sessions | length == 0`),
   and a desktop alert is dispatched via `zenity`.
5. **Unauthorized Git Commits (Failure Point 5)**: Agents concluded task runs by staging and committing
   changes unprompted. *Remedy*: Standing repository policy: never auto-commit. Working-tree diffs and status
   are presented for human review; commits remain strictly human-gated authorship.
6. **Shell Quotation Redirection Collisions (Failure Point 22)**: Commit messages generated with `<feature>`
   syntax broke zsh parsing because angle brackets were evaluated as shell redirection operators. *Remedy*:
   Strict single-quote shell escaping enforced across all automation harnesses.

### The Inward Containment Arc: Scaffolding the Agentic Pipeline

Over the last 30 days of development (October 6 – November 5, 2026), the repository's containment architecture
expanded from passive failure mitigation to active inward scaffolding—restricting the operational blast radius
of generative coding harnesses:

- **Sub-Second Pre-Flight Assertion Gates (<1s)**: To arrest out-of-distribution plays before mutating target
  hosts, every role frontloads `tasks/assert.yml` tagged `['<role>', 'assert', 'always']` (documented in
  [`docs/conventions.md`](docs/conventions.md) and [`AGENTS.md`](AGENTS.md)). The assertion suite evaluates OS
  distribution families, package managers, init systems, effective root privileges (`id -u == 0`), virtualization
  boundaries, and user identity variables in memory in under one second. Running `ansible-playbook playbooks/workstation.yml --tags assert --check`
  mechanically validates the entire control repository without modifying a single byte of disk state.
- **Quarantine of Agent Coding Harnesses**: Autonomous agent CLIs (Claude Code, OpenCode, Charm Crush,
  Antigravity) were historically co-located in general workstation tooling. To prevent recursive toolchain drift
  and privilege contamination, agent installation was divested from `roles/tools` and quarantined into standalone
  opt-in playbooks under [`playbooks/agent-harness/`](playbooks/agent-harness/). All harness plays execute with
  `become: false` as the unprivileged connection user, isolating volatile binary installations while delegating
  agent configurations, API keys, and MCP definitions strictly to Layer 2 ([yadm](https://yadm.io/)) user dotfiles.
- **Two-Stage Firstboot Lifecycle Consolidation**: System initialization was consolidated under single-role
  ownership in `roles/user` (ADR-5, ADR-6). The role maintains byte-identical parity with the
  [osbuild](https://gitlab.com/syncopatedX/osbuild) Single Source of Truth for the 7-file firstboot suite
  (`syncopated-firstboot`, `syncopated-toolchains`, autostart launchers, and profile scripts). Full-convergence
  runs establish a deterministic completion marker (`~/.initial-firstboot`, root:root 0644) in the user's home
  directory, allowing non-root console login scripts to stat verification state without requiring sudo escalation.
- **Linguistic Governance via SFL Dialectic Review**: Generative code and documentation workflows now culminate
  in formal Systemic Functional Linguistics (SFL) peer review. Specialized audit profiles (`claim-examiner`,
  `mechanism-tracer`, `evidence-auditor`, `modality-calibrator`, `relational-editor`) systematically evaluate
  technical drafts across ideational process types, interpersonal tenor, and epistemic modality—ensuring
  documentation truth matches codebase invariants and eliminating ungrounded assertions before merging.

---

## Ansible as Deterministic Execution Gate & Validator

In modern infrastructure development, probabilistic large language models excel at proposing code,
synthesizing requirements, and exploring architectural options. However, they are inherently non-deterministic.
They cannot guarantee POSIX safety, enforce idempotency, or guarantee that state mutations won't corrupt
a production machine.

Ansible serves as the **deterministic gate validator and execution engine**:

- **The AST Validation Contract**: Before any change reaches a host, Ansible validates Abstract Syntax
  Trees (AST), module argument specs (`argument_spec`), and parameter typing. Probabilistic proposals
  are mechanically verified against Ansible's formal execution schemas.
- **Sub-Second Pre-Flight Assertion Gates (<1s)**: Every role frontloads pre-flight assertions
  (`tasks/assert.yml`) tagged `[<role>, assert, always]`. If an agent proposes a playbook targeting
  the wrong OS family, missing `dnf5`, running with non-root effective UID (`id -u != 0`), or violating
  identity prerequisites, execution aborts in under one second before mutating a single byte of disk state.
- **Guaranteed Idempotency**: LLM-generated shell scripts frequently re-execute destructive operations.
  Ansible enforces declarative desired-state convergence: re-running against a converged machine yields
  zero state changes (`changed=0`).
- **Mechanical Boundary Enforcement**: Ansible enforces single file ownership, seat-aware handler execution,
  and decoupled user/system execution contexts (`local.yml` Play 1 vs Play 2), completely insulating the system
  from stochastic drift.

---

## Natural Language User Interface (NLUI) & Gherkin-Gated Pipeline

Above this deterministic execution layer sits the **Natural Language User Interface (NLUI)**. Rather
than forcing operators or autonomous agents to manually craft low-level task YAML, users express desired
workstation configurations in natural language:

```
"I need a low-latency audio workstation with Intel oneAPI SYCL acceleration,
COSMIC desktop, and containerized dev environments for Rust and Python."
```

To eliminate hallucination and parameter drift, the pipeline routes natural language intent through
**gated verification step points**:

```
[ Natural Language User Request ]
               │
               ▼ (NLUI Intent Parser)
[ Gherkin Requirement Specification Gate ]
  Feature: Low-latency Audio Workstation
    Scenario: Provision real-time kernel & SYCL toolchain
      Given an x86_64 Fedora 44 host with Intel GPU (PCI 0x8086)
      When role "tuning" and role "gpu" are converged
      Then kernel.sched_rt_runtime_us must be set to -1
       And intel-oneapi-compiler must be present
               │
               ▼ (Deterministic AST & Schema Validation)
[ Ansible Compilation & Gate Validator ]
  - tasks/assert.yml (<1s fail-fast assertion)
  - Argument specification validation
  - Single-ownership invariant verification
               │
               ▼ (Host & Image Convergence)
[ Deterministic State Execution (ansible-playbook / osbuild) ]
```

1. **Natural Language Intake**: The user expresses capabilities, hardware needs, or developer environments.
2. **Gherkin Structuring Gate**: Intent is translated into formal Gherkin (`Feature / Scenario / Given / When / Then`).
   This step forces unambiguous precondition declaration (`Given`), execution triggers (`When`), and observable
   verification targets (`Then`).
3. **Deterministic AST Compilation**: The verified Gherkin specification compiles into concrete Ansible plays,
   role tags, and role/domain variables (`gpu_install_intel_oneapi: true`, `tuning_audio_profile: true`).
4. **Pre-flight Assertion Execution**: Before execution, Ansible's assertion gates validate the hardware,
   kernel, and environment against the Gherkin contract.

---

## Converged Parity: Image Composition & Host Convergence

A fundamental architectural principle of this platform is **converged parity across target footprints**.
The exact same Ansible feature sets, roles, and validation logic drive two complementary deployment models:

1. **Declarative Base Image & Appliance Composition (Offline Build)**:
   Via the companion [osbuild](https://gitlab.com/syncopatedX/osbuild) repository, the same declarative
   definitions bake bootable ISO installers, OSTree/bootc container images, appliance disk images, and
   minimal server foundations.
2. **Active Infrastructure Convergence (Online Execution)**:
   The same roles run against active, running hosts—converging physical workstations, remote server
   distributions, and kiosk appliances to the exact declared specification via `ansible-playbook` or `ansible-pull`.

```
                    ┌─────────────────────────────────────────┐
                    │    Unified Feature Sets & Ansible Roles │
                    │   (common, tuning, networking, gpu...)  │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
    ┌───────────────────────────────┐         ┌───────────────────────────────┐
    │   Declarative Image Building  │         │   Live Host Convergence       │
    │      (companion osbuild)      │         │   (ansible-playbook / pull)   │
    ├───────────────────────────────┤         ├───────────────────────────────┤
    │ - ISO Installer Pipelines     │         │ - Bare-metal Workstations     │
    │ - bootc / OSTree Containers   │         │ - Server Distributions        │
    │ - Appliance & VM Disk Images  │         │ - Kiosk Appliances            │
    └───────────────────────────────┘         └───────────────────────────────┘
```

Because both pathways share the identical single-ownership rules, variable schemas, and package
taxonomies, a feature configured in an ISO image behaves identically to a feature converged onto a
running host after three months of uptime.

---

## Controlled Reference Distilled Dataset

This repository is intentionally structured as a **controlled reference distilled dataset** for
autonomous coding agents and LLM execution pipelines:

- **Jumping-Off Point for Autonomous Agents**: Autonomous coding agents operating in software engineering
  workflows frequently lack grounded examples of defensive infrastructure design. This repository provides
  a curated, production-proven corpus demonstrating how to structure Ansible collections for absolute safety.
- **Reference Patterns & Domain Idioms**:
  - *Tier 1 vs Tier 2 variable separation*: Eliminates cross-role leakage.
  - *Sub-second pre-flight assertions*: Validates preconditions before mutation.
  - *Seat-aware service handling*: Prevents abrupt graphical session termination.
  - *Single-ownership invariants*: Eliminates multi-role configuration flapping.
  - *Check-mode safety*: Guarantees accurate dry-run reporting with `check_mode: false` on stat/probe tasks.
- **On-Demand Task & Playbook Generation**: Agents can ingest the conventions and schemas defined here
  to synthesize custom playbooks, new role additions, or deployment orchestrations that inherit the exact
  same safety guarantees.

---

## The Architecture and Decoupling Contract

The Layer 1 orchestration surface consists of six primary entry points:

- [local.yml](local.yml) — The root-level `ansible-pull` entry point for autonomous local
  convergence. Implements two decoupled plays:
  - **Play 1: System Provisioning** (`become: true`, `--tags system`): Runs as root. Frontloads
    hardware auto-detection (KVM virtualization via `/dev/kvm`, graphical display target via
    `systemctl get-default`, container engines, and discrete CUDA/Vulkan GPUs via PCI vendor IDs
    `0x10de`, `0x8086`, `0x1002`). Executes system roles (`repos`, `common`, `tuning`, `gpu`,
    `networking`, `containerd`, `libvirt`, `theme`, `gnome`, `cosmic`, `sway`, `tools`), runs pre-flight assertions,
    and performs post-task reboot assessment (`needs-restarting -r`).
  - **Play 2: User Provisioning** (`become: false`, `become_user: workstation_user`, `--tags user`):
    Runs in unprivileged user space. Configures the user environment via `uv`, `bun`, `go`,
    `cargo`, GNOME extensions, and VS Code extensions without root contamination.
  - **The Pristine Checkpoint**: Play 1 and Play 2 are decoupled from Layer 2. The single writer
    of `~/.initial-firstboot` is `roles/user/tasks/firstboot.yml`, deployed at the conclusion of
    a full-tag run.
- [playbooks/workstation.yml](playbooks/workstation.yml) — Multi-host orchestration playbook. Imports
  [playbooks/repositories.yml](playbooks/repositories.yml) first, then targets the `workstations`
  inventory group across four modular plays.
- [playbooks/repositories.yml](playbooks/repositories.yml) — Standalone package manager and DNF
  repository configuration across Fedora and EL10 distributions, including the Negativo 17
  NVIDIA/multimedia repositories posted by default (`enable_negativo17: true`) with per-host
  Drop-in exclusion (`playbooks/files/90-negativo17-overrides.repo`).
- [playbooks/nvidia.yml](playbooks/nvidia.yml) — Standalone NVIDIA driver + CUDA + container-toolkit
  provisioning against the `workstations` group; relies on `playbooks/repositories.yml` having
  posted the Negativo 17 repositories first.
- [playbooks/nas.yml](playbooks/nas.yml) — Network-attached storage services (NFSv4, Samba, Rsync,
  firewalld) against `hosts: all`.
- [playbooks/tts.yml](playbooks/tts.yml) — Local speech synthesis (Whisper / Piper) against
  `hosts: workstations`.

### Architectural Invariants

- **Sub-Second Pre-Flight Assertions (Fail-Fast Pattern)**: Every role ships `tasks/assert.yml`,
  gated by `<role>_assert_enabled | default(true) | bool`, tagged `[<role>, assert, always]`. Validates
  distribution family, package manager (`dnf5`), init manager (`systemd`), effective UID (`id -u == 0`),
  and identity preconditions in under one second (<1s) before executing any state changes.
- **Two-Tier Variable Architecture**:
  - *Tier 1 (Host & Domain Scope)*: Semantic, unprefixed Single Source of Truth keys (`user.name`,
    `user.home`, `desktop_environment`, `enable_third_party_repos`, `workstation_path_dirs`,
    `workstation_prompt_reboot`) housed in `inventory/group_vars/` and `inventory/host_vars/`. These represent physical hardware
    and user identity. Artificial role prefixes are explicitly forbidden (`var-naming[no-role-prefix]` is skipped).
  - *Tier 2 (Role Scope)*: Variables defined in role `defaults/main.yml`, `vars/main.yml`, and `set_fact`
    must be role-prefixed (`<role>_*`) to maintain clean namespaces and prevent host variable leakage.
  - *Registered Variables*: Variables created via `register:` must be role-prefixed (`_<role>_*`)
    because registered variables possess global host scope in Ansible and collide if left generic.
- **Strict Single Ownership**: Each managed file on disk is owned by exactly one role. Grep checks
  prevent cross-role template clobbering.
- **Handler Safety**: Service restarts are guarded against session termination. Display manager
  handlers (`roles/gnome/handlers/main.yml`, `roles/cosmic/handlers/main.yml`) inspect `loginctl list-sessions` for active seats.
  Kernel-level memory tuning (`roles/tuning/tasks/zram.yml`) stages configuration and defers reloading
  to system reboot.
- **Idempotency Overrides**: Skipped installations provide explicit `*_force_install` override
  toggles (`user_bun_force_install`, `theme_force_install`, `common_yadm_force_install`).

---

## Two Commands to Converge

Validate preconditions across your entire workstation inventory in under one second without
mutating host state:

```bash
# 1. Sub-second fail-fast precondition validation (dry-run check mode)
ansible-playbook playbooks/workstation.yml --tags assert --check
```

Once assertions pass, converge the workstation to declared state:

```bash
# 2. Full workstation convergence
ansible-playbook -K playbooks/workstation.yml
```

### Pull-Based Autonomous Convergence

For local bare-metal provisioning or cloud-init bootstrap without an external control node:

```bash
# Converge privileged system configuration
sudo ansible-pull -U https://github.com/b08x/workstation.git --tags system local.yml

# Converge unprivileged user environment
ansible-pull -U https://github.com/b08x/workstation.git --tags user local.yml
```

Specific subsystems can be filtered cleanly using primary functional tags:
`--tags repos`, `--tags common`, `--tags tuning`, `--tags gpu`, `--tags networking`,
`--tags containerd`, `--tags libvirt`, `--tags theme`, `--tags gnome`, `--tags cosmic`, `--tags sway`, `--tags tools`, `--tags user`.

---

## Machine Lifecycle & Firstboot Architecture

A fresh workstation moves from bare metal to a fully converged desktop through an orchestrated
lifecycle:

```
[ Stage 0: osbuild ]
       │
       ▼ (Kickstart boot to multi-user.target)
[ Stage 1: Console Firstboot (tty1) ]
       │  - Network wait & DNF system upgrade
       │  - sudo ansible-pull -U <repo> --tags system local.yml
       │  - Hardware auto-detection & toolchain installation
       │  - Sets default target: graphical.target
       │  - Drops checkpoint: ~/.initial-firstboot
       ▼ (Reboot to graphical login)
[ Stage 2: Graphical Firstboot (XDG Autostart) ]
       │  - Auto-runs yadm clone --bootstrap (Layer 2)
       │  - Deploys user shell, dotfiles, and editor state
       │  - Drops checkpoint: ~/.local/state/syncopated/firstboot-stage2.done
       ▼
[ Converged Workstation ]
```

1. **Stage 0 (Base Image Composition)**: Built declaratively via companion
   [osbuild](https://gitlab.com/syncopatedX/osbuild) blueprints into bootable ISO appliances.
2. **Stage 1 (System Convergence)**: The kickstart boots to `multi-user.target`. First console
   login on `tty1` executes `/usr/local/bin/syncopated-firstboot` (deployed by `roles/user`).
   It executes `local.yml` via `ansible-pull`, which acts as the sole authorized writer of
   `~/.initial-firstboot` in the primary user's home directory.
3. **The Pristine Checkpoint Barrier**: The presence of `~/.initial-firstboot` locks Stage 1.
   Subsequent boots skip system provisioning.
4. **Stage 2 (User Dotfile Convergence)**: On graphical login, XDG autostart fires
   `syncopated-firstboot-user.desktop`, prompting the user to clone dotfiles via
   `yadm clone --bootstrap`. Once completed, it marks completion in
   `~/.local/state/syncopated/firstboot-stage2.done` and self-terminates.

---

## Prospective Intent & Telemetry: The llm_analyzer Framework

The repository includes a prospective evaluation and observability harness designed to analyze
Ansible task intent and generate training datasets:

- **Callback Plugin (`plugins/callback/llm_analyzer.py`)**: An opt-in notification callback.
  When enabled, it sends task YAML to a language model provider (configured via `ansible.cfg`
  or `AI_MODEL`) over a background thread pool (`ThreadPoolExecutor`), recording structured
  explanations into an append-only trace store.
- **Default Dormancy**: To ensure zero surprise latency and prevent billable API calls during
  standard runs, the callback is **commented out by default** in [ansible.cfg](ansible.cfg):

  ```ini
  stdout_callback   = rich_ci_formatter
  #callbacks_enabled = profile_tasks,llm_analyzer
  #callbacks_enabled = profile_tasks
  #callbacks_enabled = llm_analyzer
  ```

- **Deterministic Gold Label Recovery (`plugins/callback_utils/llm_metrics.py`)**: Rather than
  paying language models to evaluate language models, the offline dataset harness utilizes
  Ansible's native `ModuleArgsParser`. Because Ansible tasks are structured YAML documents,
  ground truth for 10 of 13 diagnostic fields (module name, FQCN status, parameters, conditions,
  loops, become, delegation, error handling) is extracted deterministically from the AST at
  zero token cost and zero latency.
- **Offline Dataset Generator (`scripts/llm_trainset.py`)**: Reconstructs DSPy training sets
  from stored traces, scoring structural accuracy against the deterministic parser baseline.

---

## Improvement Cycles (PDCA)

Architectural modifications follow the Plan-Do-Check-Act framework. Current ledger status:

| Cycle | Description | Status |
|:------|:------------|:-------|
| [001-llm-analyzer-dspy](docs/pdca/001-llm-analyzer-dspy.md) | llm_analyzer DSPy refactor & trace capture | Cycles 1–3 complete, Cycle 4 pending |
| [002-tuning-fail-fast-assertions](docs/pdca/002-tuning-fail-fast-assertions.md) | Tuning role fail-fast assertions | CHECK & ACT complete |
| [003-tuning-package-daemon-convergence](docs/pdca/003-tuning-package-daemon-convergence.md) | Tuning package/daemon convergence | CHECK & ACT complete |
| [004-repo-wide-fail-fast-assertions](docs/pdca/004-repo-wide-fail-fast-assertions.md) | Repository-wide fail-fast precondition assertions | CHECK & ACT complete |

---

## Working on the Repository

- **Linting & Code Quality**: Pre-commit hooks enforce formatting across Python, YAML, and Ansible:
  ```bash
  pre-commit run --all-files
  ansible-lint
  ```
- **Syntax & Check Mode**:
  ```bash
  ansible-playbook --syntax-check playbooks/workstation.yml local.yml
  ansible-playbook playbooks/workstation.yml --tags assert --check
  ```
- **Testing**:
  - `pytest -vvv -n 2`: Parallel test suite execution for callback utilities and metrics.
  - Molecule scenarios live in `extensions/molecule/` and test convergence idempotency in containers.
- **Development Containers**: Three container definitions (rootless Podman, Podman, Docker) are
  specified in `.devcontainer/` and documented in [docs/devcontainer-configuration.md](docs/devcontainer-configuration.md).

---

## The Map

The repository is organized into fourteen cohesive roles under `roles/`:

| Role | Purpose | Distribution Support | Fail-Fast Pre-Flight Assertions |
|:-----|:--------|:---------------------|:--------------------------------|
| [roles/common](roles/common/README.md) | System baseline, repository setup, hardware auto-detect, CIS L2 hardening | Fedora 44, AlmaLinux 10, Rocky Linux 10 | OS family, package manager (`dnf5`), effective root (`id -u == 0`) |
| [roles/tuning](roles/tuning/README.md) | Low-latency audio, ZRAM swap generation, sysctl, cpupower drop-ins | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Effective root, init system (`systemd`), hardware memory checks |
| [roles/networking](roles/networking/README.md) | NetworkManager profiles, DNS, interface bindings, firewall baseline | Fedora 44, AlmaLinux 10, Rocky Linux 10 | NetworkManager presence, firewall state |
| [roles/containerd](roles/containerd/README.md) | Container runtime engines (`podman`, `docker`, `none`), nerdctl | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Kernel namespace support, subuid/subgid allocation |
| [roles/libvirt](roles/libvirt/README.md) | KVM/QEMU virtualization, daemon security, virtual bridges, storage pools | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Hardware virtualization (`/dev/kvm`), libvirt group |
| [roles/theme](roles/theme/README.md) | Shared wallpapers, GTK/icon themes, cursor, font baselines | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Graphical target verification, effective root (`id -u == 0`) |
| [roles/gnome](roles/gnome/README.md) | GNOME desktop core stack, GDM display manager, seat-safe handlers | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Graphical target verification, seat-session query |
| [roles/cosmic](roles/cosmic/README.md) | COSMIC desktop environment, `cosmic-greeter`, skeleton seeding | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Graphical target verification, seat-session query |
| [roles/sway](roles/sway/README.md) | Sway / SwayFX compositor, Waybar / Eww bar engine, input/output config | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Graphical target verification, effective root (`id -u == 0`) |
| [roles/gpu](roles/gpu/README.md) | Optional hardware acceleration: Intel oneAPI/SYCL and NVIDIA CUDA stacks | Fedora 44, AlmaLinux 10, Rocky Linux 10 | PCI device detection (`0x10de`, `0x8086`), driver compiler check |
| [roles/tools](roles/tools/README.md) | Developer utilities, CLI tools, IDEs, AI coding agent harnesses, input-remapper | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Package availability, target architecture (`x86_64`) |
| [roles/user](roles/user/README.md) | Unprivileged user space: uv Python, bun, go, cargo, firstboot suite deployment | Fedora 44, AlmaLinux 10, Rocky Linux 10 | User existence, Tier 1 identity preconditions (`user.name`, `user.home`) |
| [roles/nas](roles/nas/README.md) | Storage protocols: NFSv4, Samba, Rsync, localized firewall rules | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Export directories existence, storage mount points |
| [roles/tts](roles/tts/README.md) | Local text-to-speech engine: Whisper / Piper audio pipelines | Fedora 44, AlmaLinux 10, Rocky Linux 10 | Audio subsystem, python virtualenv environment |

### Companion Repositories

| Repository | Purpose | Pipeline Status |
|:-----------|:--------|:----------------|
| [osbuild](https://gitlab.com/syncopatedX/osbuild) | Declarative image composition: ISO, appliance, disk images, realtime progress TUI | ISO pipeline functional; bootc pipeline in progress |
| [rpmbuild](https://gitlab.com/syncopatedX/rpmbuild) | Native RPM packaging: rpm_dev role, mock build chroots | Maintained |
| [llmops](https://gitlab.com/syncopatedX/llmops) | LLM telemetry and remediation: Dify, Langfuse, Hermes, Ollama | Maintained |

---

## Where to Go from Here

- **Machine Lifecycle & Bootstrap**: Read [docs/bootstrap.md](docs/bootstrap.md) for the end-to-end
  bare-metal commissioning workflow.
- **Day-to-Day Operations**: Consult [docs/usage.md](docs/usage.md) for tag filtering, targeted
  execution, and local pull techniques.
- **Layering Architecture**: Inspect [docs/layering-architecture.md](docs/layering-architecture.md)
  for layer boundaries, Gherkin gating, and ownership rules.
- **Failure Analysis**: Review [docs/failure-points.md](docs/failure-points.md) and
  [docs/conventions.md](docs/conventions.md) for the full catalog of 22 empirical failure points and their
  codified rules.
- **AI Coding Agents**: Review [AGENTS.md](AGENTS.md) thoroughly before modifying plays, variables,
  or task blocks.

---

## License

MIT — see [LICENSE](LICENSE).

Two files are carved out of the MIT grant and remain GPL with their upstream credits intact:

- [plugins/callback/llm_analyzer.py](plugins/callback/llm_analyzer.py) — GPL-3.0-or-later,
  Copyright (c) 2023 Sagi Shnaidman (derived from upstream callback plugin).
- [roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2](roles/tuning/templates/usr/lib/systemd/system/cpupower.service.j2) —
  GPL-2.0-or-later, Copyright (C) 2012-2020 Sébastien Luttringer, Copyright (C) 2024-2025
  Francesco Poli (derived from Arch Linux cpupower unit).

Vendor submodules under `vendor/` are separate works governed by their respective licenses:
`almalinux-atomic-workstation` (GPL-3.0), `finpilot` (Apache-2.0), and `osbuild` / `rpmbuild` (MIT, this stack).
