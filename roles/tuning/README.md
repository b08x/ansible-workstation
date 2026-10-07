# Ansible Role: tuning

Comprehensive workstation system tuning combining low-latency realtime audio optimizations with CachyOS performance enhancements, dynamic ZRAM memory management, udev hardware rules, and systemd manager profile drop-ins across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `tuning` role operates at **Layer 1 (Ansible Machine Orchestration)** to establish the performance baseline of the host operating system. It prepares the kernel, memory subsystem, block devices, and systemd managers for high-performance audio workloads, local LLM inference, and multi-tenant developer workflows.

```
+--------------------------------------------------------------------------+
|                     Layer 2: High-Performance Workloads                  |
|        Realtime Audio (DAWs, PipeWire, JACK), Local LLMs, Compilers      |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Layer 1: roles/tuning (Ansible)                      |
|   - Realtime PAM Security Limits (/etc/security/limits.d/41-realtime.conf)|
|   - CachyOS Sysctl Profile (/etc/sysctl.d/70-cachyos-settings.conf)      |
|   - ZRAM Generator (zstd, ram size) & Dynamic Swappiness udev Rule (150) |
|   - Udev Rules: SATA Power, Dynamic I/O Schedulers, Audio PM, Timers     |
|   - Systemd Manager Timeouts (15s/10s) & User NOFILE Limits              |
|   - Tuned Profile (throughput-performance) & CPU Governor (powersave)    |
|   - Realtime IRQ Prioritization (rtirq) & Realtime Scheduling (rtkit)    |
|   - Audio Group User Membership                                          |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Kernel                 |
|             Linux Kernel, Block Devices, CPU Power Governors             |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to composable subtask modules (`user_groups.yml`, `limits.yml`, `sysctl.yml`, `zram.yml`, `udev.yml`, `systemd.yml`, `tuned.yml`, `rtirq.yml`, `cpupower.yml`) gated by explicit boolean feature flags (`tuning_<subsystem>_enabled | default(true) | bool`).
2. **Distro-Switching Pattern (Dialect A with `first_found`)**: Dynamic OS variable inclusion utilizing `lookup('ansible.builtin.first_found')` prioritizing major-version-specific files (e.g., `Rocky-9.yml` vs `Rocky-10.yml`) before falling back to distro-wide (`Fedora.yml`, `AlmaLinux.yml`, `Rocky.yml`) or `default.yml`.
3. **Pre-flight Capability Checks**: `tasks/sysctl.yml` inspects `/proc/sys/` knob existence on the active kernel before applying parameters (`tuning_sysctl_optional`). Optional hardware/kernel keys (e.g., `dev.hpet.max-user-freq`, `kernel.unprivileged_userns_clone`) are skipped if absent, preventing fatal errors without resorting to dirty `ignore_errors: true` masks.
4. **Tag-as-Select Pattern**: Every task and include is tagged with the primary `tuning` tag and granular subsystem tags (`sysctl`, `zram`, `udev`, `systemd`, `tuned`, `cpupower`, `rtirq`, `limits`, `groups`, `packages`).
5. **Backup-on-Write Pattern**: All templated and written configuration files (`41-realtime.conf`, `70-cachyos-settings.conf`, `zram-generator.conf`, udev rules, systemd drop-ins) set `backup: true` to protect manual configurations.
6. **Handler Notification Pattern**: Changes to udev rules notify `Reload udev rules` and `Trigger udev rules`; changes to systemd drop-ins notify `Reload systemd`; service configurations notify respective restarts (`Restart zram`, `Restart tuned`, `Restart cpupower`, `Restart rtirq`, `Restart rtkit`).
7. **Two-Tier Variable Scoping**: Clean separation between Tier 1 host identity variables (`user.name`) and Tier 2 role-namespaced variables (`tuning_*`).

---

## Core Components & Optimizations

### 1. CachyOS Sysctl Profile (`tasks/sysctl.yml`)
Deploys `/etc/sysctl.d/70-cachyos-settings.conf` with balanced workstation throughput and responsiveness:
- **Memory & VFS**:
  - `vm.swappiness = 100`: High swappiness working in tandem with ZRAM compressed RAM.
  - `vm.vfs_cache_pressure = 50`: Retains directory and inode caches longer.
  - `vm.dirty_bytes = 268435456` (256 MB) & `vm.dirty_background_bytes = 67108864` (64 MB): Enforces absolute dirty byte writeback limits instead of percentage ratios, preventing multi-second I/O stalls during large file writes.
  - `vm.page-cluster = 0`: Disables swap page read-ahead for zero-latency random swap reads from ZRAM.
  - `vm.dirty_writeback_centisecs = 1500`: Flushes dirty pages every 15 seconds.
- **Kernel, Security, & IPC**:
  - `kernel.nmi_watchdog = 0`: Disables NMI watchdog to save power and eliminate latency jitter.
  - `kernel.unprivileged_userns_clone = 1`: Permits rootless container and Flatpak sandboxes.
  - `kernel.printk = "3 3 3 3"`: Suppresses low-priority kernel messages from spamming the console.
  - `kernel.kptr_restrict = 2`: Hardens kernel pointer exposure.
  - `kernel.sysrq = 1`: Retains emergency Magic SysRq access.
- **Networking & Filesystem**:
  - `net.core.netdev_max_backlog = 4096`: Increases network packet backlog queue.
  - `fs.file-max = 2097152`: Raises maximum open file descriptors.
  - `fs.inotify.max_user_watches = 524288`: Prevents inotify exhaustion in large codebases.

### 2. ZRAM Generator & Dynamic Swappiness (`tasks/zram.yml`)
- Deploys `/etc/systemd/zram-generator.conf` configuring `zram0` with `compression-algorithm = zstd` and `zram-size = ram`.
- Deploys `/etc/udev/rules.d/30-zram.rules`: Automatically triggers upon ZRAM block device initialization to boost `vm.swappiness` to `150` and disable kernel `zswap` to avoid double-compression overhead.

### 3. Hardware Udev Rules (`tasks/udev.yml`)
- **SATA Link Power** (`50-sata.rules`): Sets `power/control = on` and `link_power_management_policy = max_performance` to eliminate disk spin-up pauses.
- **Dynamic I/O Schedulers** (`60-ioschedulers.rules`):
  - Rotational HDDs: `bfq` (fair queuing and low interactive latency)
  - SATA SSDs: `mq-deadline` (deterministic multi-queue latency)
  - NVMe SSDs: `kyber` (adaptive queuing based on read/write latency targets)
- **Audio Power Management** (`20-audio-pm.rules` & `/usr/local/bin/audio-pm-ctl`): Disables `snd-hda-intel` power-saving cracks while connected to AC power and restores power saving on battery.
- **Timer Permissions** (`40-timer-permissions.rules`): Grants the `audio` group read/write access to `/dev/rtc0` and `/dev/hpet` for high-resolution MIDI and audio clocking.

### 4. Realtime Security Limits (`tasks/limits.yml`)
Configures PAM limits in `/etc/security/limits.d/41-realtime.conf` for the `audio` group:
- `rtprio: 98`: Enables SCHED_FIFO / SCHED_RR realtime thread priority.
- `memlock: unlimited`: Permits memory locking to eliminate page-fault buffer underruns (xruns).
- `nice: -20`: Grants maximum process execution priority.

### 5. Systemd Manager Settings (`tasks/systemd.yml`)
- Deploys drop-ins in `/etc/systemd/system.conf.d/00-timeout.conf` and `/etc/systemd/user.conf.d/00-timeout.conf` reducing `DefaultTimeoutStartSec` to `15s` and `DefaultTimeoutStopSec` to `10s` to eliminate hung shutdown waits.
- Configures user file descriptor limits in `/etc/systemd/user.conf.d/10-limits.conf` (`DefaultLimitNOFILE=1024:1048576`).

### 6. Tuned Profile & CPU Governor (`tasks/tuned.yml`, `tasks/cpupower.yml`)
- Configures and enables `tuned` with the `throughput-performance` profile.
- Configures `/etc/default/cpupower` and starts `cpupower.service` with the `powersave` governor (utilizing Intel HWP / AMD CPPC dynamic scaling).

### 7. Realtime IRQ Prioritization (`tasks/rtirq.yml`)
- Deploys `/etc/rtirq.conf` to prioritize sound card hardware IRQs (`snd`, `usb`) ahead of storage and network adapters.
- Enables `rtirq.service` and `rtkit-daemon.service`.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Distro Variable Loading** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky-*.yml` & `vars/Rocky.yml` |
| **ZRAM Generator** | `zram-generator` | `zram-generator` (EPEL) | `zram-generator` (EPEL) |
| **CachyOS Sysctl Profile** | Complete | Complete (with knob probe) | Complete (with knob probe) |
| **I/O Schedulers** | `kyber`, `mq-deadline`, `bfq` | `kyber`, `mq-deadline`, `bfq` | `kyber`, `mq-deadline`, `bfq` |
| **Tuned Service** | `tuned` | `tuned` | `tuned` |
| **CPU Power Service** | `kernel-tools` / `cpupower` | `kernel-tools` / `cpupower` | `kernel-tools` / `cpupower` |
| **Realtime Limits** | `/etc/security/limits.d/` | `/etc/security/limits.d/` | `/etc/security/limits.d/` |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT) added to the `audio` group. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `tuning_*` and control role-specific behavior:

#### Subsystem Activation Flags
| Variable | Default | Description |
|---|---|---|
| `tuning_groups_enabled` | `true` | Enable user group membership tasks. |
| `tuning_limits_enabled` | `true` | Enable realtime security limits configuration. |
| `tuning_udev_enabled` | `true` | Enable udev hardware and power optimization rules. |
| `tuning_sysctl_enabled` | `true` | Enable CachyOS sysctl parameter application. |
| `tuning_zram_enabled` | `true` | Enable ZRAM configuration and udev dynamic swappiness. |
| `tuning_systemd_enabled` | `true` | Enable systemd manager timeout and limit drop-ins. |
| `tuning_tuned_enabled` | `true` | Enable Tuned service and profile enforcement. |
| `tuning_rtirq_enabled` | `true` | Enable rtirq IRQ thread prioritization. |
| `tuning_rtkit_enabled` | `true` | Enable rtkit-daemon service. |
| `tuning_cpupower_enabled` | `true` | Enable CPU scaling governor configuration. |
| `tuning_irqbalance_enabled`| `false` | Enable/disable irqbalance service. |

#### Sysctl & Memory Configuration
| Variable | Default | Description |
|---|---|---|
| `tuning_sysctl_file` | `/etc/sysctl.d/70-cachyos-settings.conf` | Path to the managed sysctl drop-in file. |
| `tuning_sysctl_optional` | `['dev.hpet.max-user-freq', 'kernel.unprivileged_userns_clone']` | Sysctl keys permitted to be absent on target host. |
| `tuning_sysctl` | *(see defaults/main.yml)* | Dictionary of sysctl parameter key-value pairs. |
| `tuning_zram_device` | `"zram0"` | Name of the ZRAM device. |
| `tuning_zram_compression_algorithm` | `"zstd"` | Compression algorithm for ZRAM. |
| `tuning_zram_size` | `"ram"` | ZRAM capacity calculation formula. |
| `tuning_zram_swappiness` | `150` | Swappiness value injected upon ZRAM initialization. |

#### Hardware, Power & Systemd Configuration
| Variable | Default | Description |
|---|---|---|
| `tuning_udev_sata_enabled` | `true` | Enable SATA link power management rule. |
| `tuning_udev_sata_policy` | `"max_performance"` | SATA link power policy. |
| `tuning_udev_iosched_enabled` | `true` | Enable dynamic I/O schedulers based on drive type. |
| `tuning_udev_audio_pm_enabled` | `true` | Enable audio AC power management rule. |
| `tuning_systemd_timeout_start_sec` | `"15s"` | Systemd unit start timeout limit. |
| `tuning_systemd_timeout_stop_sec` | `"10s"` | Systemd unit stop timeout limit. |
| `tuning_systemd_user_limit_nofile` | `"1024:1048576"` | Systemd user NOFILE file descriptor limits. |
| `tuning_tuned_profile` | `"throughput-performance"`| Active tuned profile. |
| `tuning_cpupower_governor` | `"powersave"` | Active CPU scaling governor. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `tuning` | Role | Applies to all tasks within the `tuning` role. |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `groups` | Feature | Manages workstation user membership in the `audio` group. |
| `limits` | Feature | Configures PAM realtime limits in `/etc/security/limits.d/`. |
| `sysctl` | Feature | Deploys CachyOS sysctl profile and tests kernel knobs. |
| `zram` | Feature | Configures `zram-generator` and dynamic swappiness udev rules. |
| `udev` | Feature | Configures SATA, I/O scheduler, audio PM, and timer udev rules. |
| `systemd` | Feature | Deploys systemd manager timeout and limit drop-ins. |
| `tuned` | Feature | Manages tuned service and active profile. |
| `cpupower` | Feature | Deploys cpupower service and CPU governor configurations. |
| `rtirq` | Feature | Manages rtirq and rtkit realtime audio thread daemons. |
| `always` | System | Preamble debug statements and OS variable inclusion. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included in `playbooks/workstation.yml` as the first role in system provisioning:

```yaml
- name: System Configuration
  hosts: workstations
  become: true
  roles:
    - role: tuning
      tags: ["tuning", "system"]
    - role: networking
      tags: ["networking", "system"]
    - role: containerd
      tags: ["containerd", "virt"]
    - role: desktop
      tags: ["desktop", "system"]
    - role: libvirt
      tags: ["libvirt", "virt"]
```

### 2. Autonomous Local Provisioning (`local.yml`)

In `local.yml`, executed during local workstation bootstrap:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: tuning
      tags: ["tuning", "system"]
```

### 3. Execution Commands

Run full system tuning:

```bash
ansible-playbook playbooks/workstation.yml --tags "tuning"
```

Apply only CachyOS sysctl parameters:

```bash
ansible-playbook local.yml --tags "sysctl"
```

Update only ZRAM and udev optimizations:

```bash
ansible-playbook local.yml --tags "zram,udev"
```

---

## Verification & Health Checks

After role convergence, verify system tuning status:

### 1. Sysctl & Memory Verification

```bash
# Check active swappiness and dirty bytes
sysctl vm.swappiness vm.dirty_bytes vm.dirty_background_bytes

# Verify ZRAM device status and compression
zramctl

# Check active swap devices
swapon --show
```

### 2. Udev & Hardware Rules Verification

```bash
# Check active I/O schedulers across block devices
cat /sys/block/*/queue/scheduler

# Check SATA link power management policy
cat /sys/class/scsi_host/host*/link_power_management_policy

# Check RTC timer permissions
ls -l /dev/rtc0 /dev/hpet
```

### 3. Realtime Limits & User Group Verification

```bash
# Verify user limits as target user
su - {{ user.name }} -c "ulimit -r -l -e"
# Expected: rtprio 98, memlock unlimited, nice -20

# Verify group membership
groups {{ user.name }} | grep audio
```

### 4. CPU Governor & Tuned Verification

```bash
# Check active Tuned profile
tuned-adm active

# Check active CPU governor across cores
cpupower frequency-info
```

---

## Testing & Linting

Verify role syntax and standards using `ansible-lint`:

```bash
ansible-lint roles/tuning
```

Execute role unit testing via the provided test play:

```bash
ansible-playbook roles/tuning/tests/test.yml -i roles/tuning/tests/inventory --check
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
