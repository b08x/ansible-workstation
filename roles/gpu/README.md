# Ansible Role: gpu

Optional host GPU compute stacks: the Intel oneAPI toolkit (pinned MKL/compiler set) and Intel graphics drivers, plus the NVIDIA proprietary driver, CUDA toolkit, and container toolkit/CDI integration across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `gpu` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy vendor repositories, kernel driver packages, kernel command-line arguments, systemd services, and CDI container integration owned by the host.

The role was carved out of `roles/tools` (which previously carried the Intel tasks) and extended with the NVIDIA stack ported from the sibling `osbuild` repository's `nvidia` blueprint component. It runs in the **System Configuration** play of `playbooks/workstation.yml`, after `common` (which exports `detected_gpu_vendor` with the `always` tag); the standalone `playbooks/transcribe-cpp.yml` probes for oneAPI and CUDA as a consumer, never an installer.

```
+--------------------------------------------------------------------------+
|                     Layer 2: Workloads & Containers                      |
|   SYCL/HPC compilations, Whisper transcription, Podman GPU containers    |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                      Layer 1: roles/gpu (Ansible)                        |
|   - Intel oneAPI yum repo + pinned 56-entry MKL/compiler package set     |
|   - /etc/profile.d/intel-oneapi.sh profile (preserves LD_LIBRARY_PATH)   |
|   - Intel graphics driver packages (optional, non-fatal by default)       |
|   - RPM Fusion Free & Non-Free repositories (Fedora & EL)                 |
| - Negativo 17 NVIDIA driver + CUDA packages (10 of osbuild's 12 packages)|
|   - /etc/profile.d/cuda.sh environment profile (PATH & LD_LIBRARY_PATH)  |
|   - NVIDIA container toolkit, CDI script & nvidia-cdi-refresh.service    |
|   - NVIDIA power management services (suspend, hibernate, resume)        |
|   - nvidia-persistenced service (EL default on, Fedora default off)       |
|   - Kernel args via grubby + /etc/modprobe.d nouveau blacklist           |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|   GPU Vendors: NVIDIA (CUDA), Intel (oneAPI/SYCL, graphics), AMD (n/a)    |
|             Fedora 43/44, AlmaLinux 9/10, Rocky Linux 9/10               |
+--------------------------------------------------------------------------+
```

> [!NOTE]
> **Both stacks are off by default.** They are enabled per host through
> `gpu_install_intel_oneapi` (set on tinybot) and `gpu_install_nvidia`
> (set on gir). With neither flag set, the role performs no changes —
> no repositories, packages, or files.

> [!IMPORTANT]
> **Soft dependency on `roles/common`.** `common`'s hardware detection
> (tagged `always`) exports `detected_gpu_vendor`. When the `gpu` role runs
> without it (standalone invocation, `--skip-tags always`): when
> `gpu_install_nvidia` is true and `detected_gpu_vendor` is undefined, the
> assert step re-probes the vendor with an identical copy of `common`'s PCI
> sysfs scan (`roles/common/tasks/hardware.yml` — `/sys/bus/pci/devices/*`,
> class `0x03*`; `0x10de`→nvidia, `0x1002`→amd, `0x8086`→intel).
> Intel-only runs perform no vendor probe. When NVIDIA install
> is enabled but the detected vendor is not `nvidia`, the role prints a
> warning naming the vendor and skips the NVIDIA tasks; the play does not
> fail.

### Design Patterns Implemented

The role implements ten of the repository's 15 Ansible Design Patterns (canon numbering referenced at `local.yml:8-17`; the list below follows this document's own order — e.g. pre-flight assertions are canon Pattern 5):

1. **Task Dispatcher Pattern**: `tasks/main.yml` dispatches to `assert.yml`, `intel.yml`, and `nvidia.yml`, each gated by explicit boolean flags (`gpu_install_intel_oneapi`, `gpu_install_intel_graphics`, `gpu_install_nvidia`).
2. **Pre-flight Assertions (Fail-Fast Pattern)**: `tasks/assert.yml` validates facts gathered, RedHat family, supported distribution, `dnf`/`dnf5` package manager, `systemd` init manager, and effective root (`id -u` registered as `_gpu_effective_uid`), plus NVIDIA-specific gates: supported Distro-major assert (fails with `gpu: NVIDIA CUDA is not supported on <distro> <version>`), an osbuild-style NVIDIA driver **provider mutual-exclusion preflight** (classifies computed Negativo 17 URLs plus every
  `baseurl`/`mirrorlist` in the enabled sections of `/etc/yum.repos.d/*.repo`
  against the provider regex table — upstream CUDA, negativo17-lts,
  Negativo 17, RPM Fusion nvidia — and fails when more than one provider is
  configured; the Negativo 17 nvidia+multimedia pair counts as one; skip
  for the one-time hard-break migration with
  `gpu_nvidia_provider_preflight: false` — a provider section left at
  `enabled=0` is invisible to the preflight, and repo files not ending in
  `.repo` are never read), GPU vendor fallback probe, and a Secure Boot (`mokutil --sb-state`) check that warns — never fails — about the manual MOK enrollment step.
3. **Distro-Switching Pattern (`first_found`)**: The `_gpu_distro_nvidia_persistenced` default is loaded from `vars/<Distro>-<major>.yml` (Fedora-43/44, Rocky-9/10, AlmaLinux-9/10) via the `lookup('ansible.builtin.first_found')` shape used by `common` and `tuning`; the Negativo 17 repository URLs replace the former per-distro CUDA repo path and GPG key.
4. **Tag-as-Select**: Every task and include carries the `gpu` role tag plus feature tags (`intel`, `intel_oneapi`, `nvidia`, `assert`, `distro`) and the playbook-level `system` domain tag.
5. **Block-as-Unit**: Mutating groups (Intel graphics, Intel oneAPI, NVIDIA stack, CDI configuration) run as `block:` units; the Intel groups keep their `block/rescue` diagnostic structure with human-readable failure messages.
6. **Handler Notification**: Kernel argument and nouveau blacklist changes notify `gpu rebuild initramfs` (`dracut -f --regenerate-all`) and `gpu flag reboot required` (touches `/var/run/reboot-required`, read by the post-flight reboot assessment in `playbooks/workstation.yml`). The role never calls `ansible.builtin.reboot`.
7. **Two-Tier Variable Scoping**: Role defaults use `gpu_*`; internal constants and distro maps use `_gpu_*` / `_gpu_distro_*`; all registrations are `_gpu_*`-prefixed (`_gpu_effective_uid`, `_gpu_vendor`, `_gpu_nvidia_active`, `_gpu_grubby_info`, `_gpu_missing_kernel_args`).
8. **Backup-on-Write**: `/etc/profile.d/intel-oneapi.sh`, the CDI script/unit, and `/etc/modprobe.d/blacklist-nouveau.conf` are written with `backup: true`.
9. **Idempotency**: The kernel-argument step reads `grubby --info=ALL` first and only invokes `grubby --update-kernel=ALL` for arguments missing from any installed kernel, keeping reruns at `changed=0` — verify by running `ansible-playbook --tags gpu --check` twice and recording `changed=0`; the `gpu_intel_oneapi_force_install` and `gpu_nvidia_force_install` overrides force a `state: latest` re-evaluation pass over the pinned package sets.
10. **Data-Driven Configuration**: Package lists, kernel arguments, and repo URLs are variables — nothing vendor-specific is hardcoded in tasks.

---

## Core Components

Seven task units deliver the two stacks — two Intel units in `tasks/intel.yml`, the NVIDIA units in `tasks/nvidia.yml`, plus the dispatcher and assert gate (`tasks/main.yml`, `tasks/assert.yml`).

### 1. Intel Graphics Drivers (`tasks/intel.yml`)
- Installs the 7-package set (`gpu_intel_graphics_packages`) (moved from `roles/tools`).
- Failure is non-fatal by default (`gpu_intel_graphics_required: false`); the rescue prints a diagnostic and only fails the play when the required flag is set.

### 2. Intel oneAPI Toolkit (`tasks/intel.yml`)
- Imports the Intel GPG key, configures the `oneAPI` yum repository, and installs those 56 pinned entries (`gpu_intel_oneapi_packages`; unique — the pre-split `roles/tools` list carried `intel-oneapi-runtime-dpcpp-sycl-core` twice, removed at the role's creation, commit `e9a6c78`).
- Writes `/etc/profile.d/intel-oneapi.sh` to source `/opt/intel/oneapi/setvars.sh` on login.
- Preserves pre-existing `LD_LIBRARY_PATH` entries (such as CUDA or custom paths) rather than completely overriding them when sourcing `setvars.sh --force`.
- Purges any legacy unmanaged `/etc/profile.d/100-intel-oneapi.sh` script.

### 3. Negativo 17 & NVIDIA Repositories (`tasks/nvidia.yml`, `playbooks/tasks/repositories/negativo17.yml`)
- **Negativo 17 NVIDIA driver + Multimedia repositories**: defined once by the
  repositories playbook (`playbooks/tasks/repositories/negativo17.yml`) —
  `negativo17-nvidia` and `negativo17-multimedia` with the
  `RPM-GPG-KEY-slaanesh` GPG key, per-distro endpoints
  (`negativo17.org/repos/nvidia/fedora-<major>` / `epel-<major>` and the
  matching multimedia branches), and a managed priority/exclusion override
  drop-in `/etc/dnf/repos.override.d/90-negativo17-overrides.repo`
  (priority=90 on Negativo 17, `[rpmfusion*]` section-glob excludepkgs for
  `nvidia-* akmod-nvidia xorg-x11-drv-nvidia* ffmpeg* mpv* libdvdcss*
  gstreamer1-plugin*`). This reproduces the osbuild override drop-in
  (`nvidia.toml`,
  `osbuild/roles/osbuild/files/fedora/44/x86_64/components/nvidia.toml`)
  extended with a `[negativo17-multimedia]` priority section — the
  `priority=90` values and the `[rpmfusion*]` excludepkgs line
  (`nvidia-* akmod-nvidia xorg-x11-drv-nvidia* ffmpeg* mpv* libdvdcss*
  gstreamer1-plugin*`) are byte-identical, with section names adapted to
  this playbook's repo IDs — so dnf (priority 90 over 99) resolves driver
  and codec packages from Negativo 17, never RPM Fusion.
- **Posted per host**: the Negativo 17 NVIDIA packages start no NVIDIA
  service on hosts without a PCI display controller reporting vendor
  `0x10de` — the packages' own udev rules gate service start (upstream
  behavior, negativo17.org/changes-to-the-nvidia-driver-packages; not
  enforced inside this repo) — while the multimedia branch supplies codecs
  to every host at no driver cost.
- **RPM Fusion Free & Non-Free repositories**: still ensured on Fedora and EL
  (`gpu_nvidia_ensure_rpmfusion: true`) for non-driver content; the override
  drop-in makes the driver/CUDA/codec package set unresolvable from RPM Fusion.
- **Legacy official CUDA repository**: removed. The tasks/nvidia.yml
  hard-break block detects and deletes `developer.download.nvidia.com` repo
  files, erases installed `xorg-x11-drv-nvidia*` packages, and distro-syncs.
- The `nvidia-container-toolkit` repository (`nvidia.github.io/libnvidia-container`) is added only when `gpu_nvidia_container_toolkit` is true.

### 4. NVIDIA Packages & Environment (`tasks/nvidia.yml`)
- osbuild-standard Negativo 17 payload — the 10-package
  `gpu_nvidia_negativo17_packages` — installed when NVIDIA is enabled:
  `akmod-nvidia`, `cuda`, `cuda-devel`, `nvidia-driver`, `nvidia-driver-cuda`,
  `nvidia-driver-cuda-libs`, `nvidia-driver-libs`, `nvidia-settings`,
  `nvidia-persistenced`, `nvtop` (the `cuda`/`cuda-devel` pair is gated by
  `gpu_nvidia_cuda_toolkit`).
- Outside the payload, `tasks/nvidia.yml` additionally installs
  `nvidia-container-toolkit` (when `gpu_nvidia_container_toolkit`) and
  `gpu_nvidia_utils_packages` (`nvidia-settings`, `nvtop`, when
  `gpu_nvidia_utils`) — both utils names also sit in the payload, so
  `gpu_nvidia_utils: false` leaves them installed.
- Writes `/etc/profile.d/cuda.sh` configuring `PATH` and
  `LD_LIBRARY_PATH` — the role's own `[ -d /usr/local/cuda/bin ]` /
  `[ -d /usr/local/cuda/lib64 ]` guards (`tasks/nvidia.yml`, CUDA
  profile-script task) make the profile a no-op when `/usr/local/cuda` is
  absent — which it is under Negativo 17's system-path `cuda` packaging
  (upstream premise; verify on a host via `dnf repoquery -l cuda`).
- Enables the 3 systemd services (`nvidia-suspend`, `nvidia-hibernate`, `nvidia-resume`) managed by `gpu_nvidia_power_management`.

### 5. NVIDIA CDI Container Integration (`tasks/nvidia.yml`)
- Copies `nvidia-cdi-generate.sh` (0755) to `/usr/local/bin` and
  `nvidia-cdi-refresh.service` (0644) to `/etc/systemd/system` with content
  identical to the `nvidia.toml` data blocks
  (`osbuild/roles/osbuild/files/fedora/44/x86_64/components/nvidia.toml`).
- Enables the service (daemon reload, `enabled: true`) and intentionally
  leaves it **stopped** — which looks like a half-configured unit, but is
  the documented design (code comment at the enable task in
  `tasks/nvidia.yml`): the oneshot unit needs the NVIDIA module, present
  only after reboot, to generate `/etc/cdi/nvidia.yaml` for Podman.

### 6. nvidia-persistenced (`tasks/nvidia.yml`)
- The EL-on/Fedora-off asymmetry shown above resolves per-distro in
  `vars/<Distro>-<major>.yml` (loaded via Pattern 3):
  `nvidia-persistenced` is enabled on EL, disabled on Fedora; the package
  always installs.

### 7. Kernel Arguments & nouveau Blacklist (`tasks/nvidia.yml`)
- Reads `grubby --info=ALL` (`changed_when: false`) and computes which of
  the 4 kernel arguments (`gpu_nvidia_kernel_args` — `rd.driver.blacklist=nouveau`,
  `rd.driver.blacklist=nova-core`, `modprobe.blacklist=nouveau`,
  `nvidia-drm.modeset=1`) are missing from any installed kernel.
- Applies only the missing arguments via `grubby --update-kernel=ALL`
  (`changed_when` true only in that case).
- Writes `/etc/modprobe.d/blacklist-nouveau.conf`
  (`blacklist nouveau`, `options nouveau modeset=0`).
- Both changes notify `gpu rebuild initramfs` and `gpu flag reboot required`.
- **Secure Boot**: when `mokutil --sb-state` reports Secure Boot enabled, the
  role prints a warning that MOK enrollment of the NVIDIA module is a manual
  step and continues.

---

## Role Variables

### Tier 2: Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `gpu_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`). |
| `gpu_install_intel_oneapi` | `false` | Install the Intel oneAPI toolkit. |
| `gpu_intel_oneapi_packages` | *(56 pinned packages)* | Pinned oneAPI package list (overridable per host). |
| `gpu_intel_oneapi_force_install` | `false` | Force the oneAPI package set to `state: latest`. |
| `gpu_install_intel_graphics` | `false` | Install Intel graphics driver packages. |
| `gpu_intel_graphics_required` | `false` | Whether Intel graphics failure is fatal. |
| `gpu_intel_graphics_packages` | *(7 packages)* | Intel graphics driver package list. |
| `gpu_install_nvidia` | `false` | Install the NVIDIA CUDA stack. |
| `gpu_nvidia_force_install` | `false` | Force the NVIDIA driver set to `state: latest`. |
| `gpu_nvidia_cuda_toolkit` | `true` | Include `cuda`/`cuda-devel` in the Negativo 17 payload. |
| `gpu_nvidia_container_toolkit` | `true` | Install `nvidia-container-toolkit` + CDI script/unit. |
| `gpu_nvidia_utils` | `true` | Install `nvidia-settings`, `nvtop`. |
| `gpu_nvidia_utils_packages` | `nvidia-settings`, `nvtop` | NVIDIA utility package list. |
| `gpu_nvidia_ensure_rpmfusion` | `true` | Ensure RPM Fusion Free & Non-Free repositories are present (excluded-override strategy keeps driver/CUDA packages unresolvable from RPM Fusion). |
| `gpu_nvidia_provider_preflight` | `true` | Enable NVIDIA driver provider mutual-exclusion preflight. |
| `gpu_nvidia_power_management` | `true` | Enable systemd suspend/hibernate/resume power services. |
| `gpu_nvidia_power_services` | *(3 services)* | Power management service units (`nvidia-suspend`, `nvidia-hibernate`, `nvidia-resume`). |
| `gpu_nvidia_kernel_args` | *(4 osbuild args)* | Kernel command-line arguments applied via grubby. |
| `gpu_nvidia_negativo17_packages` | *(10 Negativo 17 packages)* | osbuild-standard NVIDIA driver/CUDA payload. |

### Internal (`vars/main.yml`, `vars/<Distro>-<major>.yml`)

| Variable | Description |
|---|---|
| `_gpu_nvidia_supported` | Supported `Distro-major` strings for the NVIDIA stack. |
| `_gpu_distro_nvidia_persistenced` | Per-distro nvidia-persistenced service default (EL true, Fedora false). |
| `_gpu_nvidia_container_repo_baseurl` | NVIDIA container toolkit (libnvidia-container) repository base URL (distro-independent). |
| `_gpu_nvidia_container_repo_gpgkey` | NVIDIA container toolkit repository GPG key URL (distro-independent). |

The Negativo 17 repository endpoints and the priority/exclusion override
drop-in are **not** role variables — they are owned exclusively by the
repositories playbook (`playbooks/tasks/repositories/negativo17.yml`), per the
one-owner rule.

---

## Handlers

| Handler Name | Description |
|---|---|
| `gpu rebuild initramfs` | Runs `dracut -f --regenerate-all` after kernel argument or nouveau blacklist changes. |
| `gpu flag reboot required` | Touches `/var/run/reboot-required` for the post-flight reboot assessment; the role never reboots itself. |

---

## Tags

| Tag | Scope | Description |
|---|---|---|
| `gpu` | Role | Applies to all tasks within the `gpu` role. |
| `system` | Playbook | System configuration group tag shared across system provisioning roles. |
| `assert` | Validation | Executes pre-flight assertion tasks. |
| `intel` | Feature | Intel graphics and oneAPI tasks. |
| `intel_oneapi` | Feature | Intel oneAPI toolkit tasks. |
| `nvidia` | Feature | NVIDIA driver, toolkit, container, and kernel argument tasks. |
| `negativo17` | Feature | Negativo 17 repositories and override drop-in (repositories playbook). |
| `distro` | Internal | Distribution variable loading. |
| `always` | System | Entry debug, assertions, handler flush. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks (`playbooks/workstation.yml`)

As established above, the role runs after `common`'s `always`-tagged detection; the excerpt below shows only the System Configuration play.

Excerpt — the System Configuration play (`playbooks/workstation.yml`): the play also sets `gather_facts: false`, gathers facts via an unprivileged `pre_tasks` setup, and runs four further roles; `common` runs in the preceding play.

```yaml
- name: System Configuration
  hosts: workstations
  become: true
  roles:
    - role: tuning
      tags: ["tuning", "system"]
    - role: gpu
      tags: ["gpu", "system"]
```

The standalone [`playbooks/transcribe-cpp.yml`](../../playbooks/transcribe-cpp.yml) carries the transcribe.cpp oneAPI/CUDA probes (consumer only).

### 2. Standalone NVIDIA Playbook (`playbooks/nvidia.yml`)

Provision NVIDIA display drivers, CUDA toolkit, and power management services directly on target workstations:

```bash
ansible-playbook playbooks/nvidia.yml -l gir
```

Run `playbooks/repositories.yml` first — the playbook expects the Negativo 17 repositories
(`negativo17-nvidia`, `negativo17-multimedia`) to already be posted. On hosts still carrying the
legacy upstream-CUDA / RPM Fusion stack, run once with `-e gpu_nvidia_provider_preflight=false`
to bypass the provider preflight escape hatch above during the one-time migration.

### 3. Enabling a stack per host (`inventory/host_vars/<host>.yml`)

```yaml
gpu_install_intel_oneapi: true
gpu_install_nvidia: true
```

---

## Testing & Linting

Verify role syntax and standards using:

```bash
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/workstation.yml --tags "assert" --check
ansible-lint roles/gpu
```

---

## License

MIT

## Author Information

Syncopated Workstation Team
