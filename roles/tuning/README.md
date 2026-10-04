# Ansible Role: tuning

Comprehensive workstation system tuning combining real-time audio optimizations with CachyOS performance enhancements for Fedora and Enterprise Linux (AlmaLinux, Rocky).

## Architecture & Design Patterns

This role refactors and unifies system performance tuning according to the **15 Ansible Design Patterns**:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the single dispatcher routing to modular subtask files (`user_groups.yml`, `limits.yml`, `sysctl.yml`, `zram.yml`, `udev.yml`, `systemd.yml`, `tuned.yml`, `rtirq.yml`, `cpupower.yml`).
2. **Conditional Feature Flags**: Standardized explicit boolean guards (`tuning_<subsystem>_enabled | default(true) | bool == true`) controlling each subsystem independently.
3. **Distro-Switching Pattern**: Platform packages and distro-specific configurations resolved dynamically via `vars/{{ ansible_distribution }}.yml`.
4. **Pre-flight Capability Checks**: `sysctl.yml` validates `/proc/sys` knob presence on the target host's active kernel before applying parameters, preventing fatal playbook failures on unsupported keys (e.g. `kernel.unprivileged_userns_clone`, `dev.hpet.max-user-freq`).
5. **Tag-as-Select Pattern**: Every task and include is tagged with the primary `tuning` tag and a fine-grained subfeature tag (`sysctl`, `zram`, `udev`, `systemd`, `tuned`, `cpupower`, `rtirq`, `limits`, `groups`).
6. **Backup-on-Write Pattern**: All templated and copied configuration files enable `backup: true` to prevent accidental loss of administrator customizations.
7. **Handler Notification Pattern**: Changes to udev rules reload and trigger the udev subsystem; changes to systemd drop-ins trigger `daemon-reload`; changes to service configs notify service restarts.
8. **Variable Scoping**: Role defaults and internal variables strictly adhere to the `tuning_*` namespace (Tier 2 scope) while referencing primary host identity (`user.name`) from Tier 1 SSOT.

---

## CachyOS Optimizations Included

- **Kernel Sysctl Profile** (`/etc/sysctl.d/70-cachyos-settings.conf`):
  - Memory: `vm.swappiness = 100`, `vm.vfs_cache_pressure = 50`, `vm.dirty_bytes = 268435456`, `vm.dirty_background_bytes = 67108864`, `vm.dirty_writeback_centisecs = 1500`, `vm.page-cluster = 0`.
  - Kernel & IPC: `kernel.nmi_watchdog = 0`, `kernel.unprivileged_userns_clone = 1`, `kernel.printk = "3 3 3 3"`, `kernel.kptr_restrict = 2`, `kernel.sysrq = 1`.
  - Networking & FS: `net.core.netdev_max_backlog = 4096`, `fs.file-max = 2097152`, `fs.inotify.max_user_watches = 524288`.
- **ZRAM Generator & Dynamic Swappiness**:
  - `/etc/systemd/zram-generator.conf`: Configures `zram0` with `zstd` compression and `zram-size = ram`.
  - `/etc/udev/rules.d/30-zram.rules`: Dynamically raises `vm.swappiness` to `150` upon ZRAM initialization and disables redundant kernel `zswap`.
- **Udev Hardware & Power Tuning**:
  - SATA Active Link Power Management (`/etc/udev/rules.d/50-sata.rules`): Enforces `max_performance`.
  - I/O Schedulers (`/etc/udev/rules.d/60-ioschedulers.rules`): Automatic scheduling algorithms based on rotational status and interface (`bfq` for HDD, `mq-deadline` for SATA SSD, `kyber` for NVMe).
  - Audio Power Management (`/etc/udev/rules.d/20-audio-pm.rules` & `/usr/local/bin/audio-pm-ctl`): Disables `snd-hda-intel` power-saving cracks while connected to AC power and restores power saving on battery.
  - Timer Permissions (`/etc/udev/rules.d/40-timer-permissions.rules`): Grants the `audio` group access to `/dev/rtc0` and `/dev/hpet`.
- **Systemd Manager Drop-ins**:
  - Start/Stop timeouts (`/etc/systemd/system.conf.d/00-timeout.conf` and `user.conf.d/00-timeout.conf`): Reduces service start timeout to 15s and stop timeout to 10s.
  - User Limits (`/etc/systemd/user.conf.d/10-limits.conf`): Configures `DefaultLimitNOFILE=1024:1048576`.

---

## Role Variables

| Variable | Default | Description |
|---|---|---|
| `tuning_groups_enabled` | `true` | Enable user group membership tasks |
| `tuning_limits_enabled` | `true` | Enable real-time security limits |
| `tuning_udev_enabled` | `true` | Enable udev optimization rules |
| `tuning_sysctl_enabled` | `true` | Enable sysctl parameter application |
| `tuning_zram_enabled` | `true` | Enable ZRAM configuration & udev rules |
| `tuning_systemd_enabled` | `true` | Enable systemd manager timeout & limit drop-ins |
| `tuning_tuned_enabled` | `true` | Enable Tuned service and profile enforcement |
| `tuning_rtirq_enabled` | `true` | Enable rtirq IRQ thread prioritization |
| `tuning_rtkit_enabled` | `true` | Enable rtkit-daemon service |
| `tuning_cpupower_enabled` | `true` | Enable CPU scaling governor configuration |
| `tuning_irqbalance_enabled` | `false` | Enable/disable irqbalance service |
| `tuning_sysctl_file` | `/etc/sysctl.d/70-cachyos-settings.conf` | Target sysctl drop-in path |
| `tuning_sysctl` | *(see defaults/main.yml)* | Dictionary of sysctl key-value pairs |
| `tuning_sysctl_optional` | `['dev.hpet.max-user-freq', 'kernel.unprivileged_userns_clone']` | Sysctl keys permitted to be absent on host |
| `tuning_limits` | `audio: {rtprio: 98, memlock: unlimited, nice: -20}` | PAM limits definitions |
| `tuning_udev_sata_enabled` | `true` | Enable SATA link power management |
| `tuning_udev_sata_policy` | `max_performance` | SATA link power policy |
| `tuning_udev_iosched_enabled` | `true` | Enable drive-type based I/O schedulers |
| `tuning_udev_audio_pm_enabled` | `true` | Enable audio AC power management rule |
| `tuning_udev_audio_pm_ctl_path` | `/usr/local/bin/audio-pm-ctl` | Destination path for audio-pm helper |
| `tuning_zram_device` | `zram0` | ZRAM device name |
| `tuning_zram_compression_algorithm` | `zstd` | ZRAM compression algorithm |
| `tuning_zram_size` | `ram` | ZRAM capacity calculation |
| `tuning_zram_swappiness` | `150` | Swappiness value injected upon ZRAM initialization |
| `tuning_systemd_timeout_start_sec` | `15s` | Systemd unit start timeout |
| `tuning_systemd_timeout_stop_sec` | `10s` | Systemd unit stop timeout |
| `tuning_systemd_user_limit_nofile` | `1024:1048576` | Systemd user NOFILE limits |
| `tuning_tuned_profile` | `throughput-performance` | Active tuned profile name |
| `tuning_cpupower_governor` | `powersave` | CPU governor |

---

## Example Usage

Run full tuning role:
```bash
ansible-playbook playbooks/site.yml --tags tuning
```

Run only sysctl tuning:
```bash
ansible-playbook playbooks/site.yml --tags sysctl
```

Run only ZRAM configuration:
```bash
ansible-playbook playbooks/site.yml --tags zram
```

Run only udev optimizations:
```bash
ansible-playbook playbooks/site.yml --tags udev
```

## License

GPL-2.0-or-later
