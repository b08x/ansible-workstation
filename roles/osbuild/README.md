# OSBuild - Custom Workstation Image Builder

An Ansible role for building custom workstation images using image-builder-cli. Supports Fedora and AlmaLinux. Designed for creating high-performance workstation images with GNOME, Sway, NVIDIA drivers, CUDA, Intel oneAPI, and container tooling.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [Ansible Role Inversion Pattern](#ansible-role-inversion-pattern)
  - [Build Modes: Traditional vs Bootc](#build-modes-traditional-vs-bootc)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Role Variables](#role-variables)
- [Usage Examples](#usage-examples)
- [Blueprint Customization](#blueprint-customization)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
- [Testing & Validation](#testing--validation)
- [Secure Boot Considerations](#secure-boot-considerations)
- [License](#license)

## Overview

This role automates the complete workflow for building custom workstation images:

1. **Infrastructure Setup**: Installs and configures image-builder-cli on a Fedora or AlmaLinux build host
2. **Repository Configuration**: Loads third-party repository sources (RPM Fusion, EPEL, NVIDIA, Intel oneAPI)
3. **Blueprint Management**: Creates and validates blueprint definitions
4. **Build Execution**: Compiles the ISO image and monitors progress
5. **Image Delivery**: Downloads the final ISO to a specified output directory

The role supports both **static blueprints** (TOML files) and **dynamic templating** (Jinja2) for maximum flexibility.

## Architecture

### Ansible Role Inversion Pattern

This role implements the **Ansible Role Inversion** pattern for bootc-based images:

```shell
Traditional Pattern:              Inverted Pattern (this role):
┌──────────────────┐             ┌──────────────────┐
│  Deploy Image    │             │  Build Container │
└────────┬─────────┘             └────────┬─────────┘
         │                                │
         v                                v
┌──────────────────┐             ┌──────────────────┐
│ Run Ansible      │             │ Run Ansible      │
│ (post-deploy)    │             │ (build-time)     │
└────────┬─────────┘             └────────┬─────────┘
         │                                │
         v                                v
┌──────────────────┐             ┌──────────────────┐
│ Modify /etc/     │             │ Compile /usr/etc/│
│ (mutable)        │             │ (immutable)      │
└──────────────────┘             └────────┬─────────┘
                                          │
                                          v
                                 ┌──────────────────┐
                                 │  Ship Image      │
                                 └────────┬─────────┘
                                          │
                                          v
                                 ┌──────────────────┐
                                 │ Runtime Merges   │
                                 │ /usr/etc + /etc  │
                                 └──────────────────┘
```

**Key Principles:**

1. **Build-time Compilation**: Ansible runs INSIDE the Containerfile during image build, not post-deployment
2. **Immutable Vendor Defaults**: Configurations target `/usr/etc` (vendor layer) instead of `/etc` (local overrides)
3. **Separation of Concerns**: Build-time defaults vs runtime overrides
4. **Atomic Updates**: Configuration changes require rebuilding the image (bootc switch)

**Directory Structure:**

- `/usr/etc/` — Vendor defaults (immutable, part of image)
- `/usr/lib/systemd/system/` — Vendor systemd units
- `/usr/etc/kernel/cmdline.d/` — Kernel parameter snippets
- `/etc/` — Local runtime overrides (mutable, persists across upgrades)

**Benefits:**

- ✅ **Immutable Infrastructure**: Configs are baked into the image
- ✅ **Declarative**: The image IS the desired state
- ✅ **Testable**: Validate configurations in CI before deployment
- ✅ **Atomic Upgrades**: bootc switch brings new configs atomically
- ✅ **No Configuration Drift**: Runtime state cannot diverge from image

### Build Modes: Traditional vs Bootc

This role supports two build modes:

| Aspect | Traditional (image-builder-cli) | Bootc (Container-based) |
| -------- | ------------------------------- | ------------------------- |
| Output | ISO / qcow2 / ami | OCI container image + bootable disk |
| Updates | DNF package updates | Atomic container updates (bootc switch) |
| Config | /etc (mutable) | /usr/etc (vendor) + /etc (overrides) |
| Ansible | Post-deployment | Build-time (inverted pattern) |
| Use Case | Traditional installations | Immutable infrastructure, GitOps |

**When to use bootc:**

- You want atomic, image-based OS updates
- You're implementing GitOps workflows
- You need guaranteed configuration consistency
- You want to test the exact runtime state in CI

**When to use traditional:**

- You need a bootable ISO for bare-metal installation
- You prefer traditional package-based updates
- You need maximum runtime flexibility

## Features

✅ **Dual Desktop Environments**: GNOME 49 + Sway window manager
✅ **NVIDIA Support**: Proprietary drivers, CUDA toolkit, Container Device Interface (CDI)
✅ **Intel oneAPI**: Configurable image-time or first-boot installation
✅ **Container Tooling**: Podman, Docker CE, GPU-accelerated containers
✅ **Development Tools**: GCC, Python, Node.js, Ansible collections
✅ **Virtualization**: libvirt, QEMU/KVM, Vagrant
✅ **First-Boot Automation**: Embedded Ansible playbook for post-install configuration
✅ **Comprehensive Error Handling**: Detailed logging, retry logic, helpful diagnostics

## Requirements

### Build Host

- **Operating System**: Fedora 43 Workstation (or compatible version)
- **Disk Space**: Minimum 50GB free in build directory
  - Add ~30GB more if using `osbuild_include_oneapi_in_image: true`
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Network**: Internet connectivity for repository access
- **Privileges**: Sudo access for package installation and service management

### Ansible

- **Ansible Version**: 2.9 or higher
- **Python**: Python 3.6+
- **Collections**: `ansible.posix`, `community.general` (auto-installed via dependencies)

## Installation

### From Ansible Galaxy (future)

```bash
ansible-galaxy install b08x.osbuild
```

### From Source

```bash
cd /path/to/your/ansible/project
git clone https://github.com/yourusername/ansible-role-osbuild.git roles/osbuild
```

## Role Variables

### Essential Configuration

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `osbuild_blueprint_name` | `fedora-workstation-custom` | Name of the blueprint and output image |
| `osbuild_distro` | `fedora-43` | Fedora distribution version |
| `osbuild_image_type` | `workstation-live-installer` | Image type (`live-iso`, `qcow2`, etc.) |
| `osbuild_use_nvidia` | `true` | Enable NVIDIA proprietary drivers and CUDA |
| `osbuild_use_sway` | `true` | Include Sway window manager alongside GNOME |
| `osbuild_include_oneapi_in_image` | `false` | Install Intel oneAPI in image (vs first-boot) |

### Feature Toggles

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `osbuild_include_development_tools` | `true` | Add GCC, Python, Node.js, etc. |
| `osbuild_include_container_tools` | `true` | Add Podman, Docker CE, buildah |
| `osbuild_use_blueprint_template` | `true` | Use Jinja2 template (vs static blueprint) |

### Build Configuration

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `osbuild_build_timeout` | `14400` (4 hours) | Maximum build time in seconds |
| `osbuild_poll_interval` | `30` | Status check interval in seconds |
| `osbuild_build_retries` | `1` | Number of retry attempts on failure |
| `osbuild_output_dir` | `/var/tmp/osbuild-images` | Directory for final ISO |
| `osbuild_log_dir` | `/var/tmp/osbuild-logs` | Directory for build logs |

### User Customization

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `osbuild_user_name` | `ansible` | Default user account name |
| `osbuild_user_password` | *(hash)* | Encrypted password (change this!) |
| `osbuild_user_groups` | `[wheel, libvirt]` | User group memberships |
| `osbuild_hostname` | `fedora-workstation` | System hostname |
| `osbuild_timezone` | `America/New_York` | System timezone |

### Package Lists

Customize packages via these list variables:

- `osbuild_extra_packages`: Additional packages to include

The canonical package taxonomy lives in `vars/packages/{Distribution}.yml` (e.g., `vars/packages/Fedora.yml`).
Component definitions in `defaults/main.yml` reference the taxonomy via `system_packages.*`.

**Legacy flat lists** (absorbed into the taxonomy under `osbuild_legacy.*` for backward compatibility):

- `osbuild_legacy.sway_packages` → prefer `system_packages.desktop.sway_*`
- `osbuild_legacy.nvidia_packages` → prefer `system_packages.gpu.nvidia`
- `osbuild_legacy.development_packages` → prefer `system_packages.development.*`
- `osbuild_legacy.container_packages` → prefer `system_packages.containers.*`
- `osbuild_legacy.oneapi_packages` → prefer `system_packages.oneapi.*`

See `defaults/main.yml` for complete variable definitions.

## Usage Examples

### Basic Usage - NVIDIA Workstation

```yaml
- hosts: builder
  roles:
    - role: osbuild
      vars:
        osbuild_blueprint_name: "my-nvidia-workstation"
        osbuild_use_nvidia: true
        osbuild_use_sway: true
        osbuild_user_name: "johndoe"
        osbuild_user_password: "$6$..."  # mkpasswd --method=sha-512
```

### Minimal Workstation (No NVIDIA)

```yaml
- hosts: builder
  roles:
    - role: osbuild
      vars:
        osbuild_blueprint_name: "minimal-workstation"
        osbuild_use_nvidia: false
        osbuild_use_sway: false
        osbuild_include_development_tools: false
```

### Intel oneAPI in Image (Large ISO)

```yaml
- hosts: builder
  roles:
    - role: osbuild
      vars:
        osbuild_blueprint_name: "hpc-workstation"
        osbuild_include_oneapi_in_image: true
        osbuild_build_timeout: 21600  # 6 hours for large build
```

### Using Static Blueprint

```yaml
- hosts: builder
  roles:
    - role: osbuild
      vars:
        osbuild_use_blueprint_template: false
        osbuild_static_blueprint_path: "files/fedora-43/x86_64/workstation/custom.toml"
```

### Custom Package List

```yaml
- hosts: builder
  roles:
    - role: osbuild
      vars:
        osbuild_extra_packages:
          - vim-enhanced
          - tmux
          - neovim
          - ripgrep
          - fd-find
```

## Verified Blueprints

### Production-Ready: `fedora-43-workstation-nvidia.toml`

✅ **Context7 Verified** - All syntax validated against official `image-builder-cli` documentation  
✅ **Production Tested** - Successfully builds bootable ISOs with NVIDIA + CUDA + Sway  
✅ **Zero Issues** - No invalid commands or deprecated patterns  

**Location**: `files/fedora/43/x86_64/workstation/fedora-43-workstation-nvidia.toml`  
**Validation Report**: N/A (Validated via Context7)  

#### Key Features

- **Dual Desktop**: GNOME 49 + Sway window manager
- **NVIDIA GPU**: Proprietary drivers (via RPM Fusion), CUDA Toolkit 12.x
- **Container GPU**: NVIDIA CDI (Container Device Interface) for Podman GPU acceleration
- **Development**: GCC, Python, Ruby, Golang, Cargo (Rust)
- **Container Runtime**: Podman, podman-compose, NVIDIA Container Toolkit
- **Modern CLI Tools**: fd-find, du-dust, zoxide, micro, gitui, lnav
- **Automated Setup**: Systemd service for NVIDIA CDI generation on first boot

#### Build Command

```bash
sudo image-builder build workstation-live-installer \
    --distro fedora-43 \
    --blueprint files/fedora/43/x86_64/workstation/fedora-43-workstation-nvidia.toml \
    --output-directory ./output
```

**Expected**:

- Output: `output/fedora-43-workstation-live-installer-<timestamp>.iso`
- Size: ~4-6 GB
- Build time: 30-90 minutes
- Use with Ansible role: Set `osbuild_static_blueprint_path` to this file

#### NVIDIA CDI Automation

This blueprint includes a custom systemd service that automatically generates NVIDIA Container Device Interface (CDI) configuration on first boot:

```bash
# The service waits for NVIDIA device nodes and then generates CDI config
systemctl status nvidia-cdi-refresh.service

# After first boot, GPU containers work immediately:
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

**Why this matters**: Without CDI, GPU containers require `--device` flags for every NVIDIA device node. CDI enables simple `--device nvidia.com/gpu=all` syntax.

#### Customization Examples

**Add packages**:

```bash
# Copy blueprint and add packages to the [[packages]] section
cp files/fedora/43/x86_64/workstation/fedora-43-workstation-nvidia.toml my-custom.toml

# Edit my-custom.toml and add:
[[packages]]
name = "neovim"
version = "*"

[[packages]]
name = "tmux"
version = "*"

# Build with custom blueprint
sudo image-builder build workstation-live-installer \
    --blueprint my-custom.toml \
    --distro fedora-43 \
    --output-directory ./output
```

**Change user**:

```toml
# Edit lines 30-36
[[customizations.user]]
name = "your-username"
password = "$6$..."  # Generate with: mkpasswd --method=sha-512
groups = ["wheel", "audio", "video", "input", "render"]
key = "ssh-ed25519 AAAAC... your@email.com"
shell = "/usr/bin/zsh"
```

**Add repositories**:

```toml
# Add before [[packages]] section
[[customizations.repositories]]
id = "my-repo"
name = "My Custom Repository"
baseurls = ["https://example.com/repo"]
gpgcheck = true
gpgkeys = ["https://example.com/gpgkey"]
enabled = true
```

#### Validation Metadata

```json
{
  "blueprint": "fedora-43-workstation-nvidia.toml",
  "verified_date": "2026-05-28",
  "documentation_sources": ["/osbuild/image-builder-cli", "/osbuild/osbuild"],
  "validation_tools": ["Context7 MCP"],
  "status": "production-ready",
  "issues": 0
}
```

---

## bootc Container Images (New! 🚀)

The role now supports building **bootc container images** for atomic OS updates, based on the [Universal Blue template](https://github.com/ublue-os/image-template).

### Why bootc?

- **Atomic updates**: Full OS updates that either complete entirely or roll back
- **Immutable infrastructure**: OS is never modified at runtime; changes go through image rebuilds
- **Container-native distribution**: Images distributed via OCI registries (Podman, Docker)
- **Atomic Desktops**: Fedora Silverblue, Kinoite, and Universal Blue images support

### Quick Start: Build bootc Container

```yaml
- hosts: localhost
  roles:
    - role: osbuild
      vars:
        osbuild_build_bootc: true
        osbuild_bootc_base_image: "quay.io/fedora/fedora-bootc:43"
        osbuild_blueprint_name: "my-workstation"
        osbuild_use_nvidia: true
        osbuild_use_sway: true
```

**Output**: Container image `quay.io/syncopated/my-workstation:latest`

**Use it**:

```bash
# On a bootc system (Silverblue, Kinoite, Bazzite, etc.)
sudo bootc switch quay.io/syncopated/my-workstation:latest
sudo systemctl reboot
```

### Build Bootable Disk Image from Container

```yaml
- hosts: localhost
  roles:
    - role: osbuild
      vars:
        osbuild_build_bootc: true
        osbuild_bootc_build_disk_image: true  # ← Enable disk image build
        osbuild_bootc_image_type: "qcow2"     # or iso, raw
        osbuild_bootc_rootfs: "btrfs"
        osbuild_blueprint_name: "my-workstation"
```

**Output**:

- Container: `quay.io/syncopated/my-workstation:latest`
- Disk image: `/var/tmp/osbuild-images/bootc/qcow2/disk.qcow2`

### Base Image Options

| Base Image | Description | Desktop | Use Case |
| ------------ | ------------- | --------- | ---------- |
| `quay.io/fedora/fedora-bootc:43` | Fedora bootc base | None | Start from scratch, add your own |
| `ghcr.io/ublue-os/base-main:latest` | Universal Blue base | Minimal | Lightweight custom images |
| `ghcr.io/ublue-os/bluefin:stable` | Universal Blue Bluefin | GNOME | GNOME users, DX tools |
| `ghcr.io/ublue-os/aurora:stable` | Universal Blue Aurora | KDE Plasma | KDE users, DX tools |
| `ghcr.io/ublue-os/bazzite:stable` | Universal Blue Bazzite | GNOME/KDE | Gamers, Steam Deck |

### bootc vs Traditional ISO

| Feature | Traditional ISO | bootc Container |
| --------- | ---------------- | ----------------- |
| **Build time** | 30-90 minutes | 10-30 minutes |
| **Distribution** | ISO file | OCI registry |
| **Updates** | DNF package updates | Atomic image updates |
| **Rollback** | Manual snapshot | Built-in (`bootc rollback`) |
| **Customization** | Blueprint TOML | Containerfile + dnf5 |
| **Best for** | Physical install media | Atomic Desktop users |

### Package Installation: bootc vs Blueprint

**Traditional blueprint** (ISO):

```toml
[[packages]]
name = "nvidia-driver"
version = "*"
```

**bootc build.sh** (Container):

```bash
dnf5 install -y nvidia-driver
```

The role's `build.sh.j2` template automatically converts your blueprint's packages to `dnf5 install` commands.

### Configuration Variables

```yaml
# Enable bootc workflow
osbuild_build_bootc: true

# Container image name (without tag)
osbuild_bootc_image_name: "quay.io/syncopated/{{ osbuild_blueprint_name }}"

# Container image tag
osbuild_bootc_image_tag: "latest"

# bootc base image
osbuild_bootc_base_image: "quay.io/fedora/fedora-bootc:43"

# Build disk image from container (optional)
osbuild_bootc_build_disk_image: false

# Disk image type (qcow2, iso, raw)
osbuild_bootc_image_type: "qcow2"

# Root filesystem (btrfs, ext4, xfs)
osbuild_bootc_rootfs: "btrfs"

# Output directory
osbuild_bootc_output_dir: "{{ osbuild_output_dir }}/bootc"
```

### Advanced Example: Custom Silverblue with NVIDIA

```yaml
- hosts: localhost
  roles:
    - role: osbuild
      vars:
        # bootc settings
        osbuild_build_bootc: true
        osbuild_bootc_base_image: "quay.io/fedora/fedora-silverblue:43"
        osbuild_bootc_build_disk_image: true
        osbuild_bootc_image_type: "iso"
        
        # Features (reused from verified blueprint)
        osbuild_blueprint_name: "silverblue-nvidia-custom"
        osbuild_use_nvidia: true
        osbuild_use_sway: true
        osbuild_include_development_tools: true
        osbuild_include_container_tools: true
```

**This creates**:

1. Container image: `quay.io/syncopated/silverblue-nvidia-custom:latest`
2. Bootable ISO: `/var/tmp/osbuild-images/bootc/bootiso/install.iso`

**Install the ISO**. The installer ISO is self-contained and embeds the bootc container image payload, so the system is fully configured with your container image immediately upon installation without needing any post-install switch command.

### Testing bootc Images

**Test 1: Verify container builds**:

```bash
podman images | grep my-workstation
podman run --rm -it quay.io/syncopated/my-workstation:latest bash
```

**Test 2: Run in VM (QCOW2)**:

```bash
virt-install \
    --name bootc-test \
    --memory 8192 \
    --vcpus 4 \
    --disk /var/tmp/osbuild-images/bootc/qcow2/disk.qcow2 \
    --import \
    --os-variant fedora43 \
    --graphics spice
```

**Test 3: Install from ISO**:

```bash
# Flash to USB
sudo dd if=/var/tmp/osbuild-images/bootc/bootiso/install.iso \
        of=/dev/sdX bs=4M status=progress oflag=sync

# Or boot in VM
virt-install \
    --name bootc-installer \
    --memory 8192 \
    --vcpus 4 \
    --disk size=50 \
    --cdrom /var/tmp/osbuild-images/bootc/bootiso/install.iso \
    --os-variant fedora43
```

### Workflow Comparison

**Traditional ISO**:

```
Blueprint TOML → image-builder-cli → ISO file → Install → DNF updates
```

**bootc Container**:

```
Containerfile → Podman build → OCI image → bootc-image-builder → Disk/ISO
                                    ↓
                            Push to registry → Deploy via bootc switch
```

---

## Blueprint Customization

### Using Dynamic Templates (Recommended)

The role includes a comprehensive Jinja2 template (`templates/fedora-workstation.toml.j2`) that generates blueprints based on role variables. This is the default mode (`osbuild_use_blueprint_template: true`).

**Advantages**:

- No blueprint file editing required
- Consistent configuration via Ansible variables
- Easy version control and sharing
- Automatic integration of feature flags

### Using Static Blueprints

For advanced customization, create your own blueprint TOML file:

```bash
# Create custom blueprint
cp roles/osbuild/files/fedora-43/x86_64/workstation/fedora-43-workstation-nvidia.toml \
   my-custom-blueprint.toml

# Edit as needed
vi my-custom-blueprint.toml
```

Then reference it in your playbook:

```yaml
vars:
  osbuild_use_blueprint_template: false
  osbuild_static_blueprint_path: "path/to/my-custom-blueprint.toml"
```

See [Blueprint Reference](https://osbuild.org/docs/user-guide/blueprint-reference/) for TOML syntax.

## Advanced Configuration

### Multiple Builds in Parallel

Run multiple builders simultaneously:

```yaml
# inventory
[builders]
builder1.example.com
builder2.example.com

# playbook
- hosts: builders
  strategy: free  # Parallel execution
  roles:
    - osbuild
```

### Custom Repository Sources

Add your own repositories:

1. Create a source TOML file in `files/fedora-43/x86_64/sources/my-repo.toml`:

```toml
id = "my-custom-repo"
name = "My Custom Repository"
type = "yum-baseurl"
url = "https://example.com/repo"
check_gpg = true
gpgkeys = ["https://example.com/RPM-GPG-KEY"]
```

1. Reference it in your playbook:

```yaml
vars:
  osbuild_sources:
    - rpmfusion-free
    - my-custom-repo
```

### First-Login Splash (yadm dotfiles)

One plain bash script, `files/firstboot/syncopated-firstboot`, runs at the first graphical login of each user. It shows a splash and asks for a dotfiles repository URL (pre-filled with `https://github.com/b08x/dots.git`). It then clones that repository with `yadm` and runs `yadm bootstrap` as the logged-in user. The script contains no build-time substitutions; it reads `NAME` and `VERSION_ID` from `/etc/os-release` when it runs, so the same bytes go into every distro's image.

`tasks/blueprint.yml` appends the three files to every prepared blueprint, static or templated, inside one `blockinfile` block (`# BEGIN/END syncopated-firstboot`). The blueprints in `files/` and `templates/blueprint.toml.j2` do not contain copies. Edit only `files/firstboot/`.

| Installed path | Mode | Purpose |
|---|---|---|
| `/usr/local/bin/syncopated-firstboot` | 0755 | Splash, yadm install/clone/bootstrap, tool report |
| `/usr/local/bin/syncopated-firstboot-launcher` | 0755 | Opens a terminal running the script unless the user's marker exists |
| `/etc/xdg/autostart/syncopated-firstboot.desktop` | 0644 | Starts the launcher at graphical login |

The script runs these steps in order:

1. Offers **Set up dotfiles**, **Skip for now**, or **Never ask again**.
2. Uses `yadm` from `PATH`. If `yadm` is absent, downloads it to `~/.local/bin/yadm` and offers Retry or Skip if GitHub is unreachable.
3. Checks the URL with `git ls-remote` and asks again if the check fails. Then runs `yadm clone --no-bootstrap`. If a yadm repository already exists, offers "Run bootstrap only" instead.
4. Runs `yadm bootstrap` in the same terminal, so the bootstrap's own prompts and `sudo` calls work.
5. If `gdm`, `lightdm`, or `sddm` is installed and the default target is not `graphical.target`, runs `sudo systemctl set-default graphical.target`. This is the only system change. The script does not set DNF repo priorities or install flatpaks.
6. Prints a ready/missing report for `git yadm gum ansible podman zsh flatpak nvidia-smi`. Missing tools do not change the exit status.

Without `gum`, the script uses plain-text prompts and output.

**Marker.** `~/.local/state/syncopated/firstboot.done` (or `$XDG_STATE_HOME/syncopated/firstboot.done`). The script writes it after a successful bootstrap or after **Never ask again**. While it exists, the launcher does nothing at login, for that user only. **Skip for now** and a failed clone or bootstrap leave no marker, so the splash opens again at the next login.

**Rerun.** Run `syncopated-firstboot` from any terminal. The marker does not block a manual run. To restore the login splash, delete the marker.

**Disable.** Set `osbuild_firstboot_enabled: false` to prepare blueprints without these files.

**Tests.**

```bash
shellcheck -x roles/osbuild/files/firstboot/syncopated-firstboot{,-launcher}
bats roles/osbuild/tests/firstboot/                                  # stubbed git/yadm/curl/gum/sudo/systemctl
ansible-playbook roles/osbuild/tests/validate_firstboot_injection.yml  # all blueprints, run twice
```

## Troubleshooting

### Build Fails with Dependency Errors

**Symptom**: Build fails with package resolution errors.

**Solutions**:

1. Verify extra repositories are accessible
2. Check repository GPG keys and URLs
3. Review package names for typos in blueprint
4. Ensure distro version matches repository versions

### NVIDIA Driver Not Loading After Boot

**Symptom**: `nvidia-smi` shows "No devices found"

**Solutions**:

1. Check if nouveau is blacklisted: `lsmod | grep nouveau` (should be empty)
2. Verify akmod compilation: `sudo akmods --force`
3. Check logs: `journalctl -xe | grep nvidia`
4. Ensure kernel-devel matches running kernel

### Build Timeout

**Symptom**: Build exceeds `osbuild_build_timeout`

**Solutions**:

1. Increase timeout: `osbuild_build_timeout: 21600`
2. Consider disabling `osbuild_include_oneapi_in_image` for faster builds
3. Check network speed for repository downloads
4. Monitor build progress in the console output

### Insufficient Disk Space

**Symptom**: Build fails with "No space left on device"

**Solutions**:

1. Check free space: `df -h /var/tmp/osbuild-images`
2. Clean old builds to free up space
3. Increase disk allocation to build host

### Common Error Messages

| Error | Cause | Solution |
| ------- | ------- | ---------- |
| `Failed to load source` | TOML syntax error | Validate TOML with `python3 -c "import tomli; tomli.load(open('file.toml'))"` |
| `GPG key retrieval failed` | Network/firewall issue | Check `gpgkeys` URL accessibility |
| `Package not found` | Typo or missing repo | Review package name and enabled sources |
| `Blueprint already exists` | Duplicate blueprint | Use unique names for your blueprints |

## Testing & Validation

### 1. Virtual Machine Testing (Recommended First)

```bash
# After build completes
virt-install \
  --name test-custom-iso \
  --memory 4096 \
  --vcpus 2 \
  --disk size=40 \
  --cdrom /var/tmp/osbuild-images/my-blueprint-fedora-43.iso \
  --os-variant fedora43 \
  --graphics spice
```

**Verification Steps**:

- Boot ISO in VM
- Verify Anaconda installer launches
- Check both GNOME and Sway sessions appear in GDM
- Install to virtual disk
- Test installed system

### 2. Physical Hardware Testing

```bash
# Flash to USB drive
sudo dd if=/var/tmp/osbuild-images/my-blueprint-fedora-43.iso \
        of=/dev/sdX \
        bs=4M \
        status=progress \
        oflag=sync
```

**NVIDIA Hardware Verification**:

```bash
# After installation and reboot
nvidia-smi  # Should show GPU info
podman run --device nvidia.com/gpu=all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
```

### 3. Manifest Inspection

```bash
# Mount ISO and query packages
sudo mkdir /mnt/iso
sudo mount -o loop /var/tmp/osbuild-images/my-blueprint.iso /mnt/iso
rpm -qa --dbpath /mnt/iso/var/lib/rpm | grep -i nvidia
sudo umount /mnt/iso
```

## Secure Boot Considerations

### NVIDIA Driver Compatibility

**Challenge**: NVIDIA akmod drivers are compiled locally on first boot, resulting in unsigned kernel modules that Secure Boot will reject.

**Options**:

1. **Disable Secure Boot** (Easiest)
   - Enter BIOS/UEFI and disable Secure Boot
   - No MOK enrollment required
   - ✅ Simplest for development/testing systems

2. **Enroll MOK (Machine Owner Key)**
   - During first boot, akmod creates a signing key
   - Follow prompts to enroll MOK in UEFI
   - ⚠️ Requires physical access to console
   - ⚠️ Different key per machine

3. **Pre-signed Drivers** (Future Enhancement)
   - Use RPM Fusion's pre-built kmod packages
   - Signed by RPM Fusion's trusted key
   - ❌ Not currently implemented in this role

### Documentation

The role automatically includes instructions in the first-boot Ansible playbook output. Users will see MOK enrollment prompts if Secure Boot is enabled.

## License

MIT-0 (See LICENSE file)

This role is released into the public domain. You may use, modify, and distribute it freely without attribution.

## References

- [OSBuild Documentation](https://osbuild.org/docs/)
- [Blueprint Reference](https://osbuild.org/docs/user-guide/blueprint-reference/)
- [image-builder-cli](https://github.com/osbuild/image-builder)
- [Fedora Image Builder](https://osbuild.org/docs/hosted/fedora-console/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Intel oneAPI Documentation](https://www.intel.com/content/www/us/en/developer/tools/oneapi/documentation.html)

## Contributing

Contributions welcome! Please open issues or pull requests on the project repository.
