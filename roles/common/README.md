# Common Role (`roles/common`)

System baseline role for workstation provisioning across Fedora and Enterprise Linux (AlmaLinux 10, Rocky Linux 9, and Rocky Linux 10). Establishes hardware capability auto-detection, tuned dynamic profile assignment, declarative CIS Level 2 Workstation security hardening, and an interactive terminal troubleshooting baseline.

---

## Scope & Architecture

In accordance with the workstation architecture:

- **Hardware Capability Auto-Detection (`tasks/hardware.yml`)**:
  - Probes CPU architecture, chassis type (`ansible_chassis_type`), virtualization/guest state (`is_virtual_guest`), and GPU vendors (NVIDIA, Intel, AMD).
  - Validates CUDA and Vulkan device availability.
  - Registers reusable facts (`detected_gpu_vendor`, `detected_chassis_type`, `has_cuda`, `has_vulkan`, `is_virtual_guest`, `recommended_tuned_profile`) consumed by downstream roles.
- **Tuned Daemon & Dynamic Profiling (`tasks/tuned.yml`)**:
  - Manages the `tuned` daemon.
  - Automatically activates the recommended tuned profile (`virtual-guest` on VMs, `balanced` on laptops, `accelerator-performance` on GPU workstations, `throughput-performance` on standard bare-metal), overridable via `common_tuned_profile`.
- **Declarative CIS Level 2 Workstation Hardening (`tasks/hardening/`)**:
  - Bounded `auditd` log rotation: 32 MB × 16 = 512 MB cap (`admin_space_left_action = ROTATE`, `disk_full_action = ROTATE`).
  - Desktop syscall noise filtering: eliminates high-volume events while capturing privilege escalation, identity, modules, and clock changes.
  - OpenSSH daemon hardening drop-in (`/etc/ssh/sshd_config.d/50-workstation-cis.conf`): `PermitRootLogin no`, `ClientAliveInterval 300`, `MaxAuthTries 4`.
  - System crypto policy enforcement (`DEFAULT`).
  - Restrictive umask (`027`) and core dump prevention limits.
- **Interactive Troubleshooting Baseline (`tasks/main.yml`, `tasks/zsh.yml`, `tasks/yadm.yml`)**:
  - Installs modern interactive CLI utilities (`zsh`, `fzf`, `gum`, `yadm`, `git`, `curl`, `openssh-server`, `tar`, `unzip`, `policycoreutils-python-utils`, `tuned`, `audit`).
  - Native RPM installation for `yadm` with automatic fallback to standalone binary download.
- **First-Boot Onboarding Infrastructure (`tasks/firstboot.yml`)**:
  - Deploys `syncopated-firstboot`, desktop launcher, and login hooks.
- **Decoupled Responsibilities**:
  - **Repositories & System Updates**: Decoupled into `playbooks/repositories.yml` and `playbooks/tasks/repositories/`.
  - **Developer Toolchains & Compilers**: Heavy runtimes (`golang`, `nodejs`, `npm`) and developer CLIs (`gitflow`, `inxi`, `homebrew`) are decoupled into [`roles/tools`](../tools/README.md); vendor GPU toolchains (`intel.yml` / oneAPI) are decoupled into [`roles/gpu`](../gpu/README.md).

---

## Variables

### Tier 2: Role Scope Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `common_assert_enabled` | `true` | Enable pre-flight environment, platform, and privilege assertions. |
| `common_packages_enabled` | `true` | Enable baseline interactive and system package installation. |
| `common_hardware_detection_enabled` | `true` | Enable hardware capability auto-detection. |
| `common_tuned_enabled` | `true` | Enable tuned daemon service and active profile enforcement. |
| `common_tuned_profile` | `""` | Active tuned profile name; defaults to `recommended_tuned_profile` when empty. |
| `common_hardening_enabled` | `true` | Master flag for CIS Level 2 Workstation security hardening. |
| `common_hardening_auditd_enabled` | `true` | Enable auditd bounded rotation and syscall filtering. |
| `common_hardening_sshd_enabled` | `true` | Enable SSH daemon security hardening drop-in. |
| `common_hardening_crypto_enabled` | `true` | Enable system crypto policy enforcement. |
| `common_hardening_limits_enabled` | `true` | Enable umask and core dump limits. |
| `common_auditd_max_log_file` | `32` | Maximum audit log size in MB before rotation. |
| `common_auditd_num_logs` | `16` | Number of rotated audit log files to retain (32 MB × 16 = 512 MB cap). |
| `common_auditd_space_left` | `75` | Space left warning threshold in MB. |
| `common_auditd_admin_space_left` | `50` | Admin space left threshold in MB. |
| `common_auditd_rules_immutable` | `false` | Append immutable flag (`-e 2`) to audit rules. |
| `common_sshd_permit_root_login` | `"no"` | SSH `PermitRootLogin` directive value. |
| `common_sshd_client_alive_interval` | `300` | SSH `ClientAliveInterval` in seconds. |
| `common_sshd_client_alive_count_max` | `3` | SSH `ClientAliveCountMax` timeout count. |
| `common_sshd_max_auth_tries` | `4` | Maximum authentication attempts before disconnection. |
| `common_crypto_policy` | `"DEFAULT"` | System crypto policy name. |
| `common_enforce_umask` | `true` | Deploy default restrictive umask in `profile.d`. |
| `common_default_umask` | `"027"` | Restrictive umask value. |
| `common_disable_coredumps` | `true` | Prevent unauthorized core dumps in security limits. |
| `common_yadm_url` | `"https://github.com/TheLocehiliosan/yadm/raw/master/yadm"` | Upstream download URL for standalone `yadm` fallback. |
| `common_yadm_force_install` | `false` | Force standalone `yadm` binary installation even if present. |
| `common_firstboot_enabled` | `true` | Enable firstboot onboarding desktop scripts and hooks. |

---

## Tags

| Tag | Purpose |
|---|---|
| `common` | All tasks in the common role |
| `assert` | Pre-flight assertion tasks |
| `hardware` | Hardware auto-detection tasks |
| `tuned` | Tuned daemon and profile management |
| `hardening` | CIS Level 2 Workstation security hardening tasks |
| `auditd` | Auditd rotation and rule deployment |
| `sshd` | SSH daemon configuration and service |
| `crypto` | Crypto policy enforcement |
| `limits` | Umask and core dump limits |
| `packages` | Common baseline package installation |
| `zsh` | Zsh package verification |
| `yadm` | Yadm native RPM and standalone fallback installation |
| `firstboot` | Stage 3 firstboot onboarding scripts and hooks |
