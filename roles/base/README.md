# Base Role (`roles/base`)

System foundation role for workstation provisioning across Fedora and Enterprise Linux (AlmaLinux 10, Rocky Linux 9, and Rocky Linux 10). Establishes package management, OS performance tuning, system services, hardware drivers, and core command-line utilities.

---

## Scope & Taxonomy

In accordance with the [distribution layering taxonomy](../../docs/layering-architecture.md):

- **Ansible (`roles/base`)**:
  - Manages host-level RPM foundation packages (`base_packages`) via DNF.
  - Configures DNF package manager optimizations (`fastestmirror`, `dnf-plugins-core`, metadata caching).
  - Orchestrates distribution and third-party repositories: EPEL, CRB/PowerTools, RPM Fusion (Free & Non-Free), and Fedora COPR.
  - Configures core system services: OpenSSH daemon (`sshd`) and ZRAM compressed swap (`zram-generator`).
  - Provisions Intel hardware acceleration (graphics drivers, media runtimes, firmware) and optional Intel oneAPI toolkit.
  - Installs base developer CLI utilities: `git-flow` (COPR on Fedora, source build on EL), `inxi` (package with upstream fallback), `yadm` binary bootstrap to `/usr/local/bin/yadm`, and `zsh` verification.
  - Provisions optional Homebrew (Linuxbrew) prefix at `/home/linuxbrew/.linuxbrew` (Fedora opt-in).
- **Decoupled from Base Role**:
  - **Go Toolchain & Coding Agent CLIs**: Modern Go toolchains and agent binaries (`bun`, `transcribe.cpp`, `go`, `agy`, `claude`, `crush`, `opencode`, `vibe`) are decoupled and managed by [`roles/tools`](../tools/README.md).
  - **Shell Dotfiles & Plugins**: User dotfiles (`~/.zshrc`, `~/.bashrc`), Oh-My-Zsh themes/plugins, and zoxide shell integration are managed directly by Yadm.
  - **User Accounts & Groups**: Primary user accounts, home directories, and secondary group assignments (`audio`, `video`, `render`, `input`) are managed by [`roles/user`](../user/README.md).
  - **Immutable Base Layer**: Core kernel, system runtime foundations, and container engines in bootc images are managed by OSBuild blueprints.

---

## Architecture & Design Patterns

The `base` role implements the **15 Ansible Design Patterns** to guarantee cross-distro consistency, idempotency, and clean failure behavior:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as a central dispatcher coordinating modular, single-responsibility subtask files (`dnf.yml`, `distro/`, `intel.yml`, `gitflow.yml`, `inxi.yml`, `homebrew.yml`, `zsh.yml`, `yadm.yml`).
2. **Distro-Switching Pattern**:
   - Package variable sets dynamically resolve per-major files before falling back to distro-wide files via `first_found` (e.g., `vars/Rocky-9.yml` vs `vars/Rocky-10.yml` vs `vars/AlmaLinux.yml` vs `vars/Fedora.yml`).
   - Repository setup tasks route to `tasks/distro/EL.yml` for RHEL-derivative distributions (AlmaLinux, Rocky) and `tasks/distro/Fedora.yml` for Fedora.
3. **Tag-as-Select Pattern**: Every task include and block is tagged with the primary `base` tag and specific functional tags (`packages`, `repos`, `dnf`, `epel`, `rpmfusion`, `copr`, `intel`, `gitflow`, `inxi`, `homebrew`, `zsh`, `yadm`), allowing fine-grained partial convergence.
4. **Backup-on-Write Pattern**: All templated or written configuration files (`fastestmirror.conf`, `epel.repo`, `zram-generator.conf`, `/etc/profile.d/intel-oneapi.sh`, user shell configuration files) set `backup: true` to prevent data loss.
5. **Block-as-Unit Pattern**: Tasks are organized into logical blocks paired with rescue handlers that implement standardized failure shape patterns.
6. **Conditional Feature Flags**: Subsystems are gated with explicit boolean checks (`enable_third_party_repos | default(true) | bool`, `base_enable_rpmfusion | bool`, `base_install_homebrew | bool`, `intel_oneapi_install | default(false) | bool`).
7. **Debug-as-Progress-Indicator Pattern**: Role entry logs execution start via `ansible.builtin.debug` tagged `["base", "always"]`.
8. **Handler Notification Pattern**: ZRAM configuration changes notify `Restart zram service` with virtualization guards preventing containerized failures, followed by an immediate handler flush.

---

## Error Handling & Failure Shapes

The role standardizes block-and-rescue error handling into three distinct shapes:

| Shape | Pattern | Applied To | Behavior |
|---|---|---|---|
| **Shape 1** | **Context + Hard Fail** | Base packages, EL repositories (EPEL/CRB), RPM Fusion, Intel oneAPI | Logs an actionable diagnostic message (mirror unreachable, missing upstream repo), then calls `ansible.builtin.fail` to halt playbook execution immediately. |
| **Shape 2** | **True Fallback** | `inxi` installation (`tasks/inxi.yml`) | Attempts native package installation first; if unavailable in enabled repos, rescues by downloading the standalone script directly from `codeberg.org/smxi/inxi` to `/usr/local/bin/inxi`. |
| **Shape 3** | **Optional Soft-Fail / Warning** | Intel graphics drivers (`tasks/intel.yml`), DNF repository priorities | Logs a warning message when unsupported hardware or repository conflicts occur and continues execution by default. Can be converted into a fatal failure by toggling strictness variables (`base_intel_graphics_required: true`, `base_dnf_priorities_required: true`). |

---

## Components

### 1. DNF Performance Optimization (`tasks/dnf.yml`)
- Installs `dnf-plugins-core`.
- Configures `/etc/dnf/dnf.conf` with `fastestmirror=True`.
- Deploys `/etc/dnf/plugins/fastestmirror.conf` with optimized thread and timeout parameters (`maxthreads=15`, `socket_timeout=3`).
- Refreshes metadata cache (`dnf makecache`) only when configuration values change.

### 2. Enterprise Linux Repositories (`tasks/distro/EL.yml`)
Configures package sources for AlmaLinux and Rocky Linux:
- Installs `epel-release`, `distribution-gpg-keys`, and `gnupg2`.
- Deploys managed `/etc/yum.repos.d/epel.repo` using `$releasever` parameterization for EL 9 and EL 10 compatibility.
- Enables CRB (CodeReady Builder), `highavailability`, and `rt` repository channels.
- Imports RPM Fusion Free and Non-Free GPG keys from `/usr/share/distribution-gpg-keys/rpmfusion/` matching `ansible_distribution_major_version`.
- Installs RPM Fusion Free and Non-Free release packages via dynamic `$(rpm -E %rhel)` resolution.

### 3. Fedora Repositories (`tasks/distro/Fedora.yml`)
Configures package sources for Fedora:
- Installs `python3-libdnf5`, `fedora-workstation-repositories`, and `dnf-plugins-core`.
- Installs RPM Fusion Free and Non-Free release RPMs for `ansible_distribution_major_version`.
- Enables user-specified COPR repositories from `base_copr_repos`.
- Configures repository priorities (`fedora=0`, `updates=0`, `rpmfusion-*=90`).

### 4. Base Package Installation (`tasks/main.yml`, `vars/*.yml`)
Executes a single consolidated DNF transaction for the platform's `base_packages` list:
- Core networking, compilation, compression, and diagnostic tools (`coreutils`, `git`, `fzf`, `jq`, `make`, `ninja-build`, `kitty`, `pipewire-utils`, `sox`, `tesseract-devel`, `yad`, `wl-clipboard`).
- Kernel development headers and modules (`kernel-devel`, `kernel-headers`, `kernel-modules-extra`).
- Python and Ruby build dependencies (`python3-devel`, `rbenv`, `ruby-build`, `readline-devel`, `libffi-devel`, `libyaml-devel`).

### 5. System Services & ZRAM (`tasks/main.yml`, `handlers/main.yml`)
- Enables and starts `sshd` system service.
- Configures compressed RAM swap via `/etc/systemd/zram-generator.conf` (`zram-size = RAM // 2`, `compression-algorithm = zstd`, `swap-priority = 100`).
- Triggers `systemd-zram-setup@zram0.service` restart via handler with virtualization check (`'container' not in ansible_virtualization_tech_guest`).

### 6. Intel Hardware Acceleration (`tasks/intel.yml`)
- **Graphics Drivers**: Installs `intel-media-driver`, `libva-intel-driver`, `intel-gpu-firmware`, `intel-audio-firmware`, `intel-vsc-firmware`, and `intel-vpl-gpu-rt`. Non-fatal on non-Intel hardware unless `base_intel_graphics_required: true`.
- **Intel oneAPI Toolkit**: Gated on `intel_oneapi_install: true`. Adds the official Intel repository, installs MKL and compiler runtimes (`dpcpp-cpp`, `mkl-devel`, `openmp`), and creates `/etc/profile.d/intel-oneapi.sh`.

### 7. Developer CLI Utilities
- **Git Flow (`tasks/gitflow.yml`)**: On Fedora, installs `gitflow` from COPR (`elegos/gitflow`). On Enterprise Linux, clones and installs `gitflow-avh` from source to `/usr/local/bin/git-flow`.
- **Inxi (`tasks/inxi.yml`)**: Installs the `inxi` system information tool via package manager with automatic fallback to upstream script download.
- **Yadm (`tasks/yadm.yml`)**: Downloads the latest `yadm` standalone executable to `/usr/local/bin/yadm`.
- **Zsh (`tasks/zsh.yml`)**: Validates that `zsh` is installed as the foundation shell for user space.

### 8. Homebrew / Linuxbrew (`tasks/homebrew.yml`)
- Opt-in component (`base_install_homebrew: true`, Fedora only).
- Prepares dedicated `/home/linuxbrew/.linuxbrew` prefix owned by `{{ user.name }}` and `linuxbrew` group.
- Executes official unattended Homebrew installer.
- Configures `curl_wrapper.sh` and shell resource throttling alias to avoid build hangs and CPU starvation.

---

## Distribution & Platform Matrix

| Component / Feature | Fedora (40+) | AlmaLinux 10 | Rocky Linux 10 | Rocky Linux 9 |
|---|---|---|---|---|
| **Distro Tasks** | `distro/Fedora.yml` | `distro/EL.yml` | `distro/EL.yml` | `distro/EL.yml` |
| **Package Variables** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky-10.yml` | `vars/Rocky-9.yml` |
| **Zlib Compatibility** | Distro default | `zlib-ng-compat-devel` | `zlib-ng-compat-devel` | `zlib-devel` |
| **Firewall / Bridging** | `iptables-nft` | `iptables-nft` | `iptables-nft` | `iptables-nft` |
| **Modern Utilities (`uv`, `just`)** | Distro package | Native RPM | Native RPM | Skipped (No EL9 build) |
| **Git Flow Delivery** | COPR (`elegos/gitflow`) | Source (`gitflow-avh`) | Source (`gitflow-avh`) | Source (`gitflow-avh`) |
| **Homebrew Support** | Supported (opt-in) | Not supported | Not supported | Not supported |

---

## Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) and are typically defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `enable_third_party_repos` | `true` | System-wide gate for enabling external repositories (EPEL, CRB, RPM Fusion, COPR). |
| `intel_oneapi_install` | `false` | System capability flag to install Intel oneAPI development toolkit and environment. |
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT). |
| `user.home` | `/home/{{ user.name }}` | Home directory of primary workstation user. |

### Tier 2: Role Scope Defaults (`defaults/main.yml`)

These variables are namespaced with `base_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `base_enable_rpmfusion` | `true` | Enable RPM Fusion Free and Non-Free repositories on Fedora hosts. |
| `base_copr_repos` | `[]` | List of Fedora COPR repositories (`owner/project`) to enable (e.g. `["atim/starship"]`). |
| `base_gitflow_copr` | `elegos/gitflow` | COPR repository providing the `gitflow` package on Fedora. |
| `base_install_homebrew` | `false` | Opt-in flag to install Linuxbrew into `/home/linuxbrew/.linuxbrew` (Fedora only). |
| `base_intel_graphics_required` | `false` | Strictness flag: when `true`, failure to install Intel graphics drivers fails the play. |
| `base_zoxide_required` | `false` | Strictness flag: when `true`, turns zoxide installation failure into a play failure. |
| `base_dnf_priorities_required` | `false` | Strictness flag: when `true`, turns DNF priority configuration failure into a play failure. |
| `base_my_variable` | `"default_value"` | Demonstration string variable. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for granular task execution:

| Tag | Purpose |
|---|---|
| `base` | All tasks in the base role |
| `packages` | DNF package installation and package-specific variables |
| `distro` | Distribution-specific variable and repository includes |
| `repos` / `repositories` | DNF and third-party repository configuration tasks |
| `dnf` / `mirrors` | DNF performance and `fastestmirror` plugin tasks |
| `epel` | EPEL repository installation and mirror configuration (EL) |
| `rpmfusion` | RPM Fusion Free & Non-Free GPG key and repository installation |
| `copr` | COPR repository enablement (Fedora) |
| `intel` | Intel graphics driver and media runtime installation |
| `intel_oneapi` | Intel oneAPI toolkit repository and development packages |
| `gitflow` | Git-flow package (Fedora) or source build (EL) installation |
| `inxi` | Inxi system information tool installation and fallback download |
| `homebrew` | Linuxbrew prefix, installation, and shell throttling configuration |
| `zsh` | Zsh package verification |
| `yadm` | Yadm standalone binary download |

---

## Example Usage

### 1. Inclusion in Orchestration Playbooks

Standard inclusion in `playbooks/base.yml`:

```yaml
- name: System Provisioning and Base Configuration
  hosts: workstations
  become: true
  gather_facts: true
  roles:
    - role: base
      tags: ["base", "system"]
```

### 2. Running Specific Task Subsets

Run only repository and package configuration:

```bash
ansible-playbook playbooks/site.yml --tags "repos,packages"
```

Run Intel hardware acceleration setup:

```bash
ansible-playbook playbooks/site.yml --tags "intel"
```

Provision base tools (`gitflow`, `inxi`, `yadm`):

```bash
ansible-playbook playbooks/site.yml --tags "gitflow,inxi,yadm"
```

---

## Testing & Verification

The role includes comprehensive Molecule test scenarios in `molecule/default/` tested against containerized targets:

- **Target Platforms**: Fedora, AlmaLinux 10, Rocky Linux 10, Rocky Linux 9.
- **Verification (`molecule/default/verify.yml`)**:
  - Validates `sshd` service state (`ActiveState == active`, `UnitFileState == enabled`).
  - Verifies CLI tools are executable (`git flow version`, `fzf --version`, `inxi --version`, `yadm version`).
  - Confirms Homebrew is not installed when `base_install_homebrew: false`.

Run Molecule tests:

```bash
molecule test -s default
```

Run linting:

```bash
ansible-lint roles/base
```

---

## License

GPL-2.0-or-later

## Author Information

Syncopated Workstation Team
