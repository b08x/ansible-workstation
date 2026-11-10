---
name: workstation-conventions
description: "Authoritative project conventions, structural patterns, variable scoping rules, modularity budgets, and verification contracts for the Syncopated Workstation Ansible control repository."
license: MIT
metadata:
  author: ansible-scout
  version: "1.0.0"
  category: conventions
  data_output: "reference"
---

# Workstation Conventions Skill

This skill documents the codebase architecture, role conventions, variable scoping hierarchy, assertion discipline, modularity budgets, and testing boundaries for the monolithic Ansible control repository located at `/home/b08x/WorkspaceV3/Syncopated/workstation`.

---

## 1. Repository Architecture & Inventory

### 1.1 Repository Skeleton
The repository is consolidated as a monolithic control repo:
- **`roles/`**: Standard Ansible roles (`common`, `containerd`, `desktop_ui`, `gpu`, `libvirt`, `nas`, `networking`, `tools`, `tts`, `tuning`, `user`).
- **`playbooks/`**: Controller and orchestration playbooks (`workstation.yml`, `repositories.yml`, `cargo.yml`, `nvidia.yml`, `nas.yml`, `tts.yml`, `transcribe-cpp.yml`, and `agent-harness/`).
- **`local.yml`**: Root autonomous pull playbook for `ansible-pull` and local bootstrap (implements the 15 Ansible Design Patterns).
- **`inventory/`**: Single SSOT inventory directory:
  - `inventory/hosts.yml`: Primary inventory file (set in `ansible.cfg`).
  - `inventory/group_vars/`: Global and group definitions (`all.yml`, `dev.yml`, `workstations.yml`, `headless.yml`).
  - `inventory/host_vars/`: Host-specific overrides (`gir.yml`, `tinybot.yml`, `soundbot.yml`, `ninjabot.yml`, `gir-virt.yml`).
- **`plugins/`**: Repo-local plugins (`plugins/callback/llm_analyzer.py`, `plugins/callback_utils/`).

### 1.2 Target Hosts & Disposable Testbed Target
Hosts configured in `inventory/hosts.yml`:
- **`gir`** (`192.168.41.10`): Live workstation host (`ansible_connection: local`).
- **`tinybot`** (`192.168.41.11`): Secondary workstation / remote builder.
- **`studio-cosmic`** (`192.168.41.23`): Workstation test host.
- **`gir-sway`** (`192.168.41.58`): **Dedicated disposable VM testbed** for all playbook testing, role validation, and integration runs.
- **`ninjabot`**: Headless server target.

> [!CRITICAL]
> **Host Safety Invariant**: NEVER execute mutating runs against `localhost` or live production hosts (`gir`, `tinybot`). All mutating playbook tests, integration runs, and syntax executions must target the disposable VM testbed (`gir-sway`) or run in isolated container environments.

---

## 2. Role Skeleton & Conventions

### 2.1 Standard Role Directory Layout
Every role under `roles/<role>/` strictly adheres to standard Ansible structure:
```text
roles/<role>/
├── README.md              # Role documentation and parameter description
├── meta/
│   ├── main.yml           # Galaxy metadata, dependencies, supported platforms
│   └── argument_specs.yml # Ansible 2.11+ formal argument specification
├── defaults/
│   └── main.yml           # Tier 2 default variable definitions (prefixed: <role>_*)
├── vars/
│   ├── main.yml           # Internal constant variables (prefixed: <role>_*)
│   ├── Fedora.yml         # Distribution-specific variable overrides
│   ├── AlmaLinux.yml
│   └── Rocky.yml
├── tasks/
│   ├── main.yml           # Orchestration entry point / task dispatcher
│   ├── assert.yml         # Pre-flight fail-fast environment & privilege assertion
│   └── <concern>.yml      # Modular focused task files (<= 100 lines)
├── handlers/
│   └── main.yml           # Notification handlers
├── templates/             # Jinja2 templates (.j2)
└── files/                 # Static configuration files, scripts, drop-ins
```

### 2.2 Distro Variable Loading & Dispatch Pattern
Roles maintain distribution independence through OS-specific variable mapping under `roles/<role>/vars/`:
- **Single-level lookup**:
  ```yaml
  - name: Include distribution package variables
    ansible.builtin.include_vars: "{{ ansible_distribution }}.yml"
    tags: ["<role>", "distro"]
  ```
- **Fallback / Versioned First-Found Lookup**:
  When a role requires major version branching (e.g. `roles/gpu` or `roles/tuning`):
  ```yaml
  - name: Load distribution variables
    ansible.builtin.include_vars: "{{ <role>_distro_vars }}"
    vars:
      <role>_distro_vfile: "{{ ansible_distribution }}-{{ ansible_distribution_major_version }}.yml"
      <role>_distro_vars: >-
        {{ lookup('ansible.builtin.first_found',
                  files=[<role>_distro_vfile, ansible_distribution ~ '.yml', 'default.yml'],
                  paths=role_path ~ '/vars',
                  errors='ignore') }}
    when: <role>_distro_vars is defined and <role>_distro_vars | length > 0
    tags: ["<role>", "always"]
  ```

---

## 3. Pre-flight Assertion Pattern (`assert.yml`) & Argument Specs

### 3.1 Fail-Fast Assertion Architecture
Every role implements `tasks/assert.yml` called at the top of `tasks/main.yml`. It guards against running on unsupported platforms, wrong architectures, or unprivileged user contexts before any changes occur.

```yaml
# In roles/<role>/tasks/main.yml:
- name: Validate pre-flight assertions and platform support
  ansible.builtin.include_tasks: assert.yml
  when: <role>_assert_enabled | default(true) | bool
  tags: ["<role>", "assert", "always"]
```

### 3.2 Canonical `assert.yml` Anatomy
A compliant `assert.yml` includes:
1. **Fact Gathering Check**:
   ```yaml
   - name: Assert Ansible facts are gathered
     ansible.builtin.assert:
       that:
         - ansible_os_family is defined
         - ansible_distribution is defined
       fail_msg: >-
         Ansible facts must be gathered before executing the <role> role.
       quiet: true
     tags: ["<role>", "assert", "always"]
   ```
2. **Platform & Package Manager Support**:
   ```yaml
   - name: Assert supported OS family and distribution
     ansible.builtin.assert:
       that:
         - ansible_os_family == 'RedHat'
         - ansible_distribution in ['Fedora', 'AlmaLinux', 'Rocky', 'RedHat', 'CentOS']
       fail_msg: "Unsupported platform {{ ansible_distribution }}."
       quiet: false
     tags: ["<role>", "assert", "always"]

   - name: Assert package manager is DNF
     ansible.builtin.assert:
       that:
         - ansible_pkg_mgr in ['dnf', 'dnf5']
       fail_msg: "Detected package manager '{{ ansible_pkg_mgr }}' is not supported."
       quiet: true
     tags: ["<role>", "assert", "always"]
   ```
3. **Effective UID Verification (`_<role>_effective_uid`)**:
   - For system/root-level roles:
     ```yaml
     - name: Verify target host effective user ID
       ansible.builtin.command: id -u
       register: _<role>_effective_uid
       changed_when: false
       check_mode: false
       tags: ["<role>", "assert", "always"]

     - name: Assert target host execution privilege is root
       ansible.builtin.assert:
         that:
           - _<role>_effective_uid.stdout | trim == '0'
         fail_msg: >-
           The <role> role requires root privileges. Effective UID is {{ _<role>_effective_uid.stdout | trim }}.
         quiet: true
       tags: ["<role>", "assert", "always"]
     ```
   - For user-level roles (`roles/user`):
     ```yaml
     - name: Verify workstation user effective UID
       ansible.builtin.command: id -u
       register: _user_effective_uid
       changed_when: false
       check_mode: false
       tags: ["user", "assert", "always"]

     - name: Assert workstation user UID matches configured user
       ansible.builtin.assert:
         that:
           - user.uid is not defined or _user_effective_uid.stdout | trim | int == user.uid | int
         fail_msg: "Mismatch in effective user UID."
         quiet: true
       tags: ["user", "assert", "always"]
     ```

### 3.3 Argument Specification (`meta/argument_specs.yml`)
Roles document their parameters using Ansible's `meta/argument_specs.yml`:
```yaml
---
argument_specs:
  main:
    short_description: <Role Description>
    options:
      <role>_assert_enabled:
        type: bool
        description: Enable pre-flight environment, platform, and privilege assertions.
        default: true
      <role>_some_flag:
        type: bool
        description: Enable or disable feature X.
        default: false
```

---

## 4. Variable Scoping & Naming Discipline

The repository enforces strict two-tier scoping:

### 4.1 Tier 1: Host & Domain Variables (SSOT, Unprefixed)
- **Scope**: Defined in `inventory/group_vars/` (e.g. `all.yml`, `dev.yml`) or `inventory/host_vars/` (e.g. `gir.yml`, `tinybot.yml`).
- **Convention**: Semantic, unprefixed names representing machine hardware, primary user identity, or host capabilities.
- **Rule Exemption**: `var-naming[no-role-prefix]` is explicitly skipped in `.ansible-lint` to preserve semantic SSOT definitions without forced role prefixing.
- **Examples**:
  - `user.name`, `user.home`, `user.shell`, `user.uid`, `user.gid`, `user.secondary_groups`
  - `enable_desktop: true`
  - `intel_oneapi_install: false`
  - `nvidia_cuda_install: true`
  - `containerd_use_podman: true`
  - `containerd_use_docker: false`
  - `workstation_prompt_reboot: false`

### 4.2 Tier 2: Role-Scoped Variables (Prefixed `<role>_*`)
- **Scope**: Defined in `roles/<role>/defaults/main.yml`, `roles/<role>/vars/main.yml`, or internal `set_fact`.
- **Convention**: MUST start with `<role>_` to prevent namespace collisions across plays.
- **Examples**:
  - `common_packages_enabled`, `common_tuned_enabled`, `common_tuned_profile`
  - `desktop_ui_environment`, `desktop_ui_greeter`, `desktop_ui_packages`
  - `tools_vscode_force_install`, `tools_install_flatpaks`
  - `tuning_cpupower_governor`, `tuning_irqbalance_enabled`

### 4.3 Registered Variables (Private Convention `_<role>_*`)
- **Scope**: Created during playbook/task execution via `register:`.
- **Convention**: Registered variables have global host scope in Ansible. To prevent leaking across roles, private registered variables MUST use `_<role>_<descriptor>`:
  - `_common_effective_uid`
  - `_desktop_ui_effective_uid`
  - `_reboot_check_rhel`
  - `tools_vscode_check` (or `_tools_vscode_check`)

---

## 5. User File Ownership & Templating Pattern

Managing `$HOME/.config/` and dotfiles follows clear separation of privileges:

### 5.1 Direct User Context (`become_user: "{{ user.name }}"`)
When managing files directly in the workstation user's home directory:
```yaml
- name: Ensure pip config directory exists
  ansible.builtin.file:
    path: "{{ user.home | default('/home/' + user.name) }}/.config/pip"
    state: directory
    owner: "{{ user.name }}"
    group: "{{ user.name }}"
    mode: "0755"

- name: Enforce require-virtualenv for pip
  community.general.ini_file:
    path: "{{ user.home | default('/home/' + user.name) }}/.config/pip/pip.conf"
    section: global
    option: require-virtualenv
    value: "true"
    owner: "{{ user.name }}"
    group: "{{ user.name }}"
    mode: "0644"
    backup: true
```

### 5.2 Task Inclusion Dispatch with `apply`
In `roles/user/tasks/main.yml`, modular tasks run under user privilege using `apply`:
```yaml
- name: Include uv configuration tasks
  ansible.builtin.include_tasks:
    file: uv.yml
    apply:
      become: true
      become_user: "{{ user.name }}"
  when: user_install_uv | default(true) | bool
  tags: ["uv", "user"]
```

### 5.3 Skeleton Seeding Pattern (`/etc/skel/.config/`)
For system-wide default user configurations (e.g. desktop configs in `roles/desktop_ui/tasks/cosmic/environment.yml`), files are staged in `/etc/skel/.config/` with root ownership so subsequent user provisioning inherits clean defaults:
```yaml
- name: Ensure COSMIC skeleton directories exist in /etc/skel
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    owner: root
    group: root
    mode: "0755"
  loop:
    - /etc/skel/.config/cosmic
    - /etc/skel/.config/cosmic/com.system76.CosmicTheme.Mode/v1

- name: Seed default COSMIC theme mode skeleton configuration
  ansible.builtin.copy:
    dest: /etc/skel/.config/cosmic/com.system76.CosmicTheme.Mode/v1/mode
    content: "Dark"
    owner: root
    group: root
    mode: "0644"
```

### 5.4 System vs User Boundary Separation
- User toolchains (`cargo`, `go`, `bun`, `uv`, shell dotfiles) execute in **user context** (`become_user: "{{ user.name }}"`).
- Firstboot machine suite (`roles/user/tasks/firstboot.yml`) executes in **root context** (`become_user: root`), deploying `/usr/local/bin` and `/etc/profile.d` scripts, while writing the convergence marker to the primary user's home (`~/.initial-firstboot`).

---

## 6. Modularity Budgets (Sandi Metz for Ansible)

To guarantee readability, debuggability, and testability, all tasks and playbooks must adhere to strict modularity budgets:

| Budget Metric | Limit | Rationale |
|---|---|---|
| **Task file lines** | ≤ 100 lines | Prevents monolithic sprawl; isolates single concerns |
| **Tasks per file** | ≤ 10 tasks | Keeps execution trace bounded and comprehensible |
| **Task operational logic** | ≤ 5 lines | Module arguments and complex data belong in vars/defaults |
| **Module arguments** | ≤ 4 parameters | Complex configs should be structured in YAML dictionaries |
| **Playbook purity** | 1 primary role per play | Entry playbooks act as controllers/orchestrators |

### Modularity Baseline Findings (Repository Audit)
- **Total role task files**: 85 files.
- **Files within budget**: 74 files (87.1% compliance).
- **Files exceeding budget (> 100 lines / > 10 tasks)**:
  1. `roles/user/tasks/gnome-extensions.yml`: 388 lines, 24 tasks *(Refactoring candidate for Phase 3)*
  2. `roles/user/tasks/assert.yml`: 325 lines, 22 tasks *(Extract sub-assert modules)*
  3. `roles/user/tasks/go.yml`: 302 lines, 16 tasks *(Split install, GOPATH, and binary setup)*
  4. `roles/gpu/tasks/nvidia.yml`: 250 lines, 1 task *(Large block task)*
  5. `roles/gpu/tasks/assert.yml`: 217 lines, 7 tasks *(Split CUDA vs Intel assertion paths)*
  6. `roles/nas/tasks/nfs/firewall.yml`: 155 lines, 11 tasks
  7. `roles/user/tasks/vscode-extensions.yml`: 153 lines, 13 tasks
  8. `roles/common/tasks/hardware.yml`: 126 lines, 1 task
  9. `roles/nas/tasks/packages.yml`: 124 lines, 11 tasks
  10. `roles/nas/tasks/assert.yml`: 109 lines, 10 tasks
  11. `roles/desktop_ui/tasks/cosmic/greeter.yml`: 106 lines, 10 tasks

---

## 7. Layer Boundaries & System Ownership

The workstation ecosystem is structured into four distinct layers:

1. **OS / Image Builder Layer** (`~/WorkspaceV3/Syncopated/osbuild`):
   - Owns base RPM packages, kernel drivers, systemd units, filesystem partitioning, SELinux policies, and initial ostree/bootc images.
2. **Ansible System Layer** (This repository - Root context):
   - Owns host-wide tuning (`tuned`, `sysctl`), GPU driver enablement (CUDA repos, Intel oneAPI), virtualization (`libvirtd`, `qemu`), display manager (`gdm` vs `cosmic-greeter`), system flatpaks, and firewall ports.
3. **Ansible User Layer** (This repository - User context):
   - Owns developer tools, user environment dotfiles, toolchains (`uv`, `go`, `bun`, `cargo`), GNOME/COSMIC user settings, and application configs under `$HOME/.config/`.
4. **Isolated / Ephemeral Testbed Layer**:
   - Disposable testbed VM (`gir-sway`) and container sandboxes for hermetic execution.

---

## 8. Verification Commands & Quality Gates

All development must be verified using the repository's deterministic read-only checks:

### 8.1 Playbook Syntax Checks
```bash
# Verify workstation entry playbook syntax
ansible-playbook playbooks/workstation.yml --syntax-check

# Verify local pull playbook syntax
ansible-playbook local.yml --syntax-check
```

### 8.2 Pre-flight Assertion Check (Dry Run / Fail-Fast)
```bash
# Run all role assertions across hosts without executing mutations
ansible-playbook playbooks/workstation.yml --tags assert --check
```

### 8.3 Ansible Linting
```bash
# Execute lint check from repo root
ansible-lint
```
> [!NOTE]
> `.ansible-lint` configures exclusions for vendor collections and skips `var-naming[no-role-prefix]` for Tier 1 semantic variables.

### 8.4 Git Status & Scope Check
```bash
# Verify working tree cleanliness
git status -s -b
```
