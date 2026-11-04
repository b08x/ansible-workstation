# Ansible Role: gpu

Optional host GPU compute stacks: the Intel oneAPI toolkit (pinned MKL/compiler set) and Intel graphics drivers, plus the NVIDIA proprietary driver, CUDA toolkit, and container toolkit/CDI integration across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `gpu` role operates at **Layer 1 (Ansible Machine Orchestration)** to deploy vendor repositories, kernel driver packages, kernel command-line arguments, systemd services, and CDI container integration owned by the host.

The role was carved out of `roles/tools` (which previously carried the Intel tasks) and extended with the NVIDIA stack ported from the sibling `osbuild` repository's `nvidia` blueprint component. It runs in the **System Configuration** play of `playbooks/workstation.yml`, after `common` (which exports `detected_gpu_vendor` with the `always` tag) and before `tools` (whose `transcribe-cpp.yml` probes for oneAPI and CUDA as a consumer, never an installer).

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
|   - /etc/profile.d/intel-oneapi.sh environment profile                   |
|   - Intel graphics driver packages (optional, non-fatal by default)       |
|   - NVIDIA CUDA repo (fedora43/fedora44/rhel9/rhel10) + GPG key          |
|   - NVIDIA driver, CUDA toolkit, container toolkit, utilities             |
|   - NVIDIA CDI generation script + nvidia-cdi-refresh.service             |
|   - nvidia-persistenced service (EL default on, Fedora default off)       |
|   - Kernel args via grubby + /etc/modprobe.d nouveau blacklist           |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Hardware               |
|   GPU Vendors: NVIDIA (CUDA), Intel (oneAPI/SYCL, graphics), AMD (n/a)    |
|             Fedora 43/44, AlmaLinux 10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

> [!NOTE]
> **Both stacks are off by default.** They are enabled per host through the
> Tier 1 inventory flags `intel_oneapi_install` (existing; set on tinybot)
> and `nvidia_cuda_install` (new). With neither flag set, the role performs
> no changes — no repositories, packages, or files.

> [!IMPORTANT]
> **Soft dependency on `roles/common`.** `common`'s hardware detection
> (tagged `always`) exports `detected_gpu_vendor`. When the `gpu` role runs
> without it (standalone invocation, `--skip-tags always`), its assert step
> re-probes the GPU vendor via the same PCI sysfs scan. When NVIDIA install
> is enabled but the detected vendor is not `nvidia`, the role prints a
> warning naming the vendor and skips the NVIDIA tasks; the play does not
> fail.

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` dispatches to `assert.yml`, `intel.yml`, and `nvidia.yml`, each gated by explicit boolean flags (`gpu_install_intel_oneapi`, `gpu_install_intel_graphics`, `gpu_install_nvidia`) that lazily consume the Tier 1 host flags.
2. **Pre-flight Assertions (Fail-Fast Pattern)**: `tasks/assert.yml` validates facts gathered, RedHat family, supported distribution, `dnf`/`dnf5` package manager, `systemd` init manager, and effective root (`id -u` registered as `_gpu_effective_uid`), plus NVIDIA-specific gates: supported Distro-major assert (fails with `gpu: NVIDIA CUDA is not supported on <distro> <version>`), GPU vendor fallback probe, and a Secure Boot (`mokutil --sb-state`) check that warns — never fails — about the manual MOK enrollment step.
3. **Distro-Switching Pattern (`first_found`)**: CUDA repo path, GPG key, and the `nvidia-persistenced` default are loaded from `vars/<Distro>-<major>.yml` (Fedora-43/44, Rocky-9/10, AlmaLinux-10) via the `lookup('ansible.builtin.first_found')` shape used by `common` and `tuning`.
4. **Tag-as-Select**: Every task and include carries the `gpu` role tag plus feature tags (`intel`, `intel_oneapi`, `nvidia`, `assert`, `distro`) and the playbook-level `system` domain tag.
5. **Block-as-Unit**: Mutating groups (Intel graphics, Intel oneAPI, NVIDIA stack, CDI configuration) run as `block:` units; the Intel groups keep their `block/rescue` diagnostic structure with human-readable failure messages.
6. **Handler Notification**: Kernel argument and nouveau blacklist changes notify `gpu rebuild initramfs` (`dracut -f --regenerate-all`) and `gpu flag reboot required` (touches `/var/run/reboot-required`, read by the post-flight reboot assessment in `playbooks/workstation.yml`). The role never calls `ansible.builtin.reboot`.
7. **Two-Tier Variable Scoping**: Tier 1 unprefixed host flags (`intel_oneapi_install`, `nvidia_cuda_install`) are consumed lazily by Tier 2 `gpu_*` defaults; all registrations are `_gpu_*`-prefixed (`_gpu_effective_uid`, `_gpu_vendor`, `_gpu_nvidia_active`, `_gpu_grubby_info`, `_gpu_missing_kernel_args`).
8. **Backup-on-Write**: `/etc/profile.d/intel-oneapi.sh`, the CDI script/unit, and `/etc/modprobe.d/blacklist-nouveau.conf` are written with `backup: true`.
9. **Idempotency**: The kernel-argument step reads `grubby --info=ALL` first and only invokes `grubby --update-kernel=ALL` for arguments missing from any installed kernel, keeping reruns at `changed=0`; the `gpu_intel_oneapi_force_install` and `gpu_nvidia_force_install` overrides force a `state: latest` re-evaluation pass over the pinned package sets.
10. **Data-Driven Configuration**: Package lists, kernel arguments, repo paths, and GPG keys are variables — nothing vendor-specific is hardcoded in tasks.

---

## Core Components

### 1. Intel Graphics Drivers (`tasks/intel.yml`)
- Installs the `gpu_intel_graphics_packages` set (moved from `roles/tools`).
- Failure is non-fatal by default (`gpu_intel_graphics_required: false`); the rescue prints a diagnostic and only fails the play when the required flag is set.

### 2. Intel oneAPI Toolkit (`tasks/intel.yml`)
- Imports the Intel GPG key, configures the `oneAPI` yum repository, and installs the pinned `gpu_intel_oneapi_packages` list (56 unique entries; the tools list's duplicate `intel-oneapi-runtime-dpcpp-sycl-core` entry removed).
- Writes `/etc/profile.d/intel-oneapi.sh` to source `/opt/intel/oneapi/setvars.sh` on login.
- Behavior is identical to the former `roles/tools/tasks/intel.yml`; a host can override the package list without editing the role.

### 3. NVIDIA Repositories (`tasks/nvidia.yml`)
- `cuda-<path>-x86_64` yum repository with the per-distro GPG key
  (`fedora43`/`1940C73E.pub`, `fedora44`/`73CD9B30.pub`,
  `rhel9`/`rhel10` with `CDF6BA43.pub`), mirroring the osbuild `nvidia`
  component. **No RPM Fusion repository is added** — the proprietary driver
  resolves exclusively from the NVIDIA CUDA repo.
- The `nvidia-container-toolkit` repository (`nvidia.github.io/libnvidia-container`) is added only when `gpu_nvidia_container_toolkit` is true.

### 4. NVIDIA Packages (`tasks/nvidia.yml`)
- Driver set always installed when NVIDIA is enabled:
  `nvidia-driver`, `nvidia-driver-cuda`, `nvidia-driver-cuda-libs`,
  `nvidia-driver-libs`, `nvidia-gpu-firmware`, `nvidia-persistenced`.
- `cuda-toolkit`, `nvidia-container-toolkit`, and the utilities
  (`nvidia-settings`, `nvtop`) each gated by their own boolean toggle.

### 5. NVIDIA CDI Container Integration (`tasks/nvidia.yml`)
- Copies `nvidia-cdi-generate.sh` (0755) to `/usr/local/bin` and
  `nvidia-cdi-refresh.service` (0644) to `/etc/systemd/system` with content
  identical to the osbuild `nvidia.toml` data blocks.
- Enables the service (daemon reload, `enabled: true`) and intentionally
  leaves it **stopped**: the oneshot unit runs at boot and needs the NVIDIA
  module loaded to generate `/etc/cdi/nvidia.yaml` for Podman.

### 6. nvidia-persistenced (`tasks/nvidia.yml`)
- Package always installed with the driver set; the systemd service is
  enabled only when `gpu_nvidia_persistenced` is true (EL defaults true,
  Fedora defaults false, matching the osbuild component's service list).

### 7. Kernel Arguments & nouveau Blacklist (`tasks/nvidia.yml`)
- Reads `grubby --info=ALL` (`changed_when: false`) and computes which of
  `gpu_nvidia_kernel_args` (`rd.driver.blacklist=nouveau`,
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

### Tier 1: Host & Domain Scope Variables (inventory `host_vars`/`group_vars`)

| Variable | Default | Description |
|---|---|---|
| `intel_oneapi_install` | *(undefined → false)* | Enable the Intel oneAPI toolkit on this host (set on tinybot). |
| `nvidia_cuda_install` | *(undefined → false)* | Enable the NVIDIA CUDA stack on this host. |

### Tier 2: Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `gpu_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`). |
| `gpu_install_intel_oneapi` | `{{ intel_oneapi_install | default(false) | bool }}` | Install the Intel oneAPI toolkit. |
| `gpu_intel_oneapi_packages` | *(56 pinned packages)* | Pinned oneAPI package list (overridable per host). |
| `gpu_intel_oneapi_force_install` | `false` | Force the oneAPI package set to `state: latest`. |
| `gpu_install_intel_graphics` | `false` | Install Intel graphics driver packages. |
| `gpu_intel_graphics_required` | `false` | Whether Intel graphics failure is fatal. |
| `gpu_intel_graphics_packages` | *(7 packages)* | Intel graphics driver package list. |
| `gpu_install_nvidia` | `{{ nvidia_cuda_install | default(false) | bool }}` | Install the NVIDIA CUDA stack. |
| `gpu_nvidia_force_install` | `false` | Force the NVIDIA driver set to `state: latest`. |
| `gpu_nvidia_cuda_toolkit` | `true` | Install `cuda-toolkit`. |
| `gpu_nvidia_container_toolkit` | `true` | Install `nvidia-container-toolkit` + CDI script/unit. |
| `gpu_nvidia_utils` | `true` | Install `nvidia-settings`, `nvtop`. |
| `gpu_nvidia_utils_packages` | `nvidia-settings`, `nvtop` | NVIDIA utility package list. |
| `gpu_nvidia_persistenced` | *(from `vars/<distro>.yml`)* | Enable the `nvidia-persistenced` service (EL true, Fedora false). |
| `gpu_nvidia_kernel_args` | *(4 osbuild args)* | Kernel command-line arguments applied via grubby. |
| `gpu_nvidia_driver_packages` | *(6 packages)* | NVIDIA driver packages always installed when enabled. |

### Internal (`vars/main.yml`, `vars/<Distro>-<major>.yml`)

| Variable | Description |
|---|---|
| `gpu_nvidia_supported` | Supported `Distro-major` strings for the NVIDIA stack. |
| `gpu_nvidia_cuda_repo_path` | CUDA repository path segment (`fedora43`, `fedora44`, `rhel9`, `rhel10`). |
| `gpu_nvidia_cuda_gpgkey` | CUDA repository GPG key filename (`1940C73E.pub`, `73CD9B30.pub`, `CDF6BA43.pub`). |
| `gpu_nvidia_container_repo_baseurl` | NVIDIA container toolkit (libnvidia-container) repository base URL (distro-independent). |
| `gpu_nvidia_container_repo_gpgkey` | NVIDIA container toolkit repository GPG key URL (distro-independent). |

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
| `distro` | Internal | Distribution variable loading. |
| `always` | System | Entry debug, assertions, handler flush. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks (`playbooks/workstation.yml`)

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

The role runs after `common` (hardware detection) and before `tools`
(transcribe.cpp oneAPI/CUDA probes).

### 2. Enabling a stack per host (`inventory/host_vars/<host>.yml`)

```yaml
intel_oneapi_install: true
nvidia_cuda_install: true
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
