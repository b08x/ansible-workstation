# Ansible Role: desktop

Provisions the graphical workstation environment, display server libraries, system-wide GNOME shell extensions, Google Antigravity Hub & IDE, Visual Studio Code, hardware key remapping, and system-scoped Flatpaks across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `desktop` role operates at **Layer 1 (Ansible Machine Orchestration)** to provision the graphical display environment and system-level administrative desktop tools, while delegating user-space productivity applications to **Layer 2 (Yadm)**.

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Unprivileged User Desktop Apps (~/bootstrap.d/80-install-user-flatpaks.sh):|
|   Obsidian, Typora, Audacity, fre:ac, Helvum, Podman Desktop, DBeaver    |
|   VS Code Extensions (~/.config/yadm/bootstrap.d/91-install-vscode-extensions.sh) |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Layer 1: roles/desktop (Ansible)                     |
|   - Display Toolkits: Qt5/Qt6 & GTK3/GTK4 Runtime Libraries              |
|   - Desktop Environment: GNOME Core Stack & Graphical Target Target      |
|   - GNOME Extensions: DNF System Packages & dconf State Management        |
|   - Themes: Yaru Theme Suite (DNF on Fedora; Meson/Ninja Source on EL)   |
|   - System Flatpaks: Flathub Remote + Admin Tools (Flatseal, Warehouse)  |
|   - Developer IDEs: VS Code (Native RPM/Flatpak) & Antigravity Hub/IDE   |
|   - Hardware Utilities: Input-Remapper Daemon & Python Services          |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                  Layer 0: Host Operating System & Kernel                 |
|             Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10                 |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

The role adheres strictly to the **15 Ansible Design Patterns** established for this repository:

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as the primary dispatcher routing execution to modular subtask files (`gnome.yml`, `theme.yml`, `flatpak.yml`, `vscode.yml`, `antigravity.yml`, `input-remapper.yml`).
2. **Distro-Switching Pattern (Dialect A)**: Dynamic OS-specific variable inclusion via `vars/{{ ansible_distribution }}.yml`, defining distribution packages (`desktop_packages.qt`, `gtk`, `gnome`, `theme`) cleanly without inline conditional mess.
3. **Failure-Shape Pattern (Shape 1: Context Re-raise)**:
   - `tasks/theme.yml`: Catches failures in both Fedora DNF installation and Enterprise Linux source builds (meson/ninja), outputs diagnostic repository/compilation context, and cleanly halts execution via `ansible.builtin.fail`.
4. **Tag-as-Select Pattern**: Every task include and block is tagged with the primary `desktop` tag and fine-grained feature tags (`gnome`, `theme`, `flathub`, `flatpaks`, `vscode`, `antigravity`, `input-remapper`, `packages`).
5. **Backup-on-Write Pattern**: Managed configuration files (`/etc/yum.repos.d/vscode.repo`, `/opt/antigravity/.installed_url`) specify `backup: true` to prevent accidental overwrites.
6. **Handler Notification Pattern**: Changes to service unit files (such as input-remapper) notify `Daemon reload` (`systemd daemon-reload`).
7. **User Context Isolation (`become_user`)**: User-scoped configurations (GNOME extension dconf state) execute directly under `become_user: "{{ user.name }}"` to ensure appropriate permissions in user schemas.
8. **Pre-flight Idempotency Tracking**: Antigravity Hub and IDE verify previously extracted archive URLs via `.installed_url` stat and slurp checks, skipping redundant network downloads and extraction.
9. **Pre-flight Assertion Pattern**: Frontloads system requirement verification (`tasks/assert.yml`) to fail fast when prerequisites (OS family, DNF package manager, effective root privileges, desktop environment) are not met.

---

## Core Components & Subsystems

### 1. Display Toolkits & Graphical Server (`tasks/main.yml`, `tasks/gnome.yml`)
- Deploys Qt runtime libraries (`qt5`, `qt6`, `qt5ct`, `qt6ct`, `qscintilla-qt5`) and GTK libraries (`gtk4`, `gtk3-devel`, `gtksourceview4`, `gtksourceview5`).
- On GNOME hosts (`desktop_environment == 'gnome'`), installs the GNOME desktop environment package groups (`@gnome-desktop`, `@graphical-server-environment`, `gdm`, `gnome-tweaks`).
- Inspects systemd default target and promotes to `graphical.target` when not already set.

### 2. GNOME Shell Extensions (Layer 2 Bootstrap)
- GNOME extensions have been decoupled from the system Ansible role and are managed idempotently via Layer 2 yadm bootstrap (`~/.config/yadm/bootstrap.d/40-gnome-extensions.sh`).
- Parses extensions from `~/.config/yadm/files/gnome-extensions.txt`.
- Dynamically discovers and installs missing DNF packages and validates UUID enablement status.

### 3. Desktop Theming (`tasks/theme.yml`)
- Checks `/usr/share/themes/Yaru` directory via `ansible.builtin.stat` to skip redundant installation or source builds when the theme is already present.
- Supports forcing re-installation/re-build via `desktop_theme_force_install: true`.
- **Fedora**: Installs the complete Ubuntu Yaru theme family from DNF packages (`yaru-theme`, `gnome-shell-theme-yaru`, `yaru-gtk*-theme`, `yaru-icon-theme`, `yaru-sound-theme`).
- **Enterprise Linux (AlmaLinux & Rocky Linux)**: Installs build dependencies, clones the upstream Yaru theme repository, and compiles/installs system-wide via `meson setup build` and `ninja -C build install`.

### 4. System Management Flatpaks (`tasks/flatpak.yml`)
- Configures the official Flathub remote repository (`https://dl.flathub.org/repo/flathub.flatpakrepo`) under system scope (`method: system`).
- Deploys administrative and system-management Flatpaks:
  - `com.mattjakeman.ExtensionManager`: Extension Manager (GNOME shell extension browser and updater)
  - `com.github.tchx84.Flatseal`: Flatseal (Flatpak permission manager)
  - `io.github.flattool.Warehouse`: Warehouse (Flatpak application and leftover file manager)
  - `io.github.dvlv.boxbuddyrs`: BoxBuddy (GUI manager for Distrobox containers)

### 5. Visual Studio Code (`tasks/vscode.yml`)
- Checks for existing `code` binary in `$PATH` to ensure idempotency and skip redundant repository and package operations when already present.
- Supports native RPM installation (default) or Flatpak distribution (`desktop_vscode_flatpak: true`).
- Supports forcing re-installation via `desktop_vscode_force_install: true`.
- Configures Microsoft's official yum repository and GPG signing key (`https://packages.microsoft.com/keys/microsoft.asc`).
- User-space VS Code extensions have been decoupled from the system Ansible role and are managed idempotently via Layer 2 yadm bootstrap (`~/.config/yadm/bootstrap.d/91-install-vscode-extensions.sh`).

### 6. Google Antigravity Hub & IDE (`tasks/antigravity.yml`)
- Provisions the Google Antigravity Hub (`/opt/antigravity`) and IDE (`/opt/antigravity-ide`) from official release tarballs.
- Employs `.installed_url` state markers to track deployed builds and prevent re-downloading identical archives.
- Creates standard Freedesktop desktop entries (`antigravity.desktop` and `antigravity-ide.desktop`) in `/usr/share/applications/`.
- Supports clean uninstallation when `desktop_antigravity_state: absent`.

### 7. Input Remapper (`tasks/input-remapper.yml`)
- Checks `/etc/systemd/system/input-remapper.service`.
- When missing, provisions required Python libraries (`evdev`, `pydantic`, `dasbus`, `PyGObject`, `psutil`), clones the upstream repository, and installs the service using Python installer hooks.
- Enables and starts the `input-remapper` systemd daemon.

---

## Distribution & Platform Matrix

| Feature / Capability | Fedora (40+) | AlmaLinux (9 & 10) | Rocky Linux (9 & 10) |
|---|---|---|---|
| **Distro Variable File** | `vars/Fedora.yml` | `vars/AlmaLinux.yml` | `vars/Rocky.yml` |
| **Qt & GTK Runtimes** | DNF packages | DNF packages | DNF packages |
| **GNOME Desktop** | `@gnome-desktop`, `gdm` | `@gnome-desktop`, `gdm` | `@gnome-desktop`, `gdm` |
| **Yaru Theme Strategy** | DNF Package install | Meson/Ninja source build | Meson/Ninja source build |
| **System Flathub Remote** | Supported (`method: system`) | Supported (`method: system`) | Supported (`method: system`) |
| **VS Code Delivery** | Microsoft DNF Repo or Flatpak | Microsoft DNF Repo or Flatpak | Microsoft DNF Repo or Flatpak |
| **Antigravity Hub & IDE** | `/opt` tarball deployment | `/opt` tarball deployment | `/opt` tarball deployment |
| **Input-Remapper** | Source build & systemd daemon | Source build & systemd daemon | Source build & systemd daemon |

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT) used for dconf and user-level tools. |
| `auto_enable_desktop` | `true` | Capability flag evaluated during `local.yml` preflight checks to determine whether to include the desktop role on graphical systems. |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `desktop_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `desktop_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`) to fail fast on invalid environments. |
| `desktop_environment` | `"gnome"` | Target desktop environment (e.g. `"gnome"`). |
| `desktop_system_flatpaks` | *(4 packages)* | System management Flatpaks (`ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy`). |
| `desktop_vscode_flatpak` | `false` | When true, installs VS Code via Flatpak instead of native DNF package. |
| `desktop_vscode_force_install` | `false` | When true, forces installation even if `code` binary is already present. |
| `desktop_theme_force_install` | `false` | When true, forces theme installation/build even if `/usr/share/themes/Yaru` is present. |
| `desktop_antigravity_state` | `"present"` | State of Antigravity Hub and IDE installation (`present` or `absent`). |
| `desktop_antigravity_hub_url` | *(Google storage URL)* | Download URL for Antigravity Hub archive. |
| `desktop_antigravity_ide_url` | *(Google storage URL)* | Download URL for Antigravity IDE archive. |


### Tier 2: Distribution Variables (`vars/*.yml`)

Loaded dynamically from `vars/{{ ansible_distribution }}.yml`:

| Variable | Type | Description |
|---|---|---|
| `desktop_packages.qt` | `list` | Distribution-specific Qt5 and Qt6 runtime packages. |
| `desktop_packages.gtk` | `list` | Distribution-specific GTK3 and GTK4 packages. |
| `desktop_packages.gnome` | `list` | Distribution package groups and tools for GNOME desktop. |
| `desktop_packages.theme` | `list` | Theme packages on Fedora; build dependencies on Enterprise Linux. |

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `desktop` | Role | Applies to all tasks within the `desktop` role. |
| `assert` | Validation | Executes pre-flight assertion tasks to validate system requirements and privileges. |
| `packages` | Feature | Targets Qt, GTK, and GNOME DNF package installation. |
| `gnome` | Feature | Executes GNOME desktop configuration and display target promotion. |
| `extensions` | Feature | Manages GNOME Shell extensions installation and dconf enablement. |
| `theme` | Feature | Provisions Yaru desktop and shell themes (DNF or source build). |
| `flathub` | Feature | Ensures system Flathub remote repository is configured. |
| `flatpaks` | Feature | Deploys system administrative Flatpaks. |
| `vscode` | Feature | Provisions Visual Studio Code repository, package, and extensions. |
| `antigravity` | Feature | Installs or removes Google Antigravity Hub and IDE. |
| `input-remapper` | Feature | Builds and configures input-remapper systemd daemon. |
| `always` | System | Preamble debug statements and OS variable inclusion. |

---

## Playbook Integration & Usage

### 1. Inclusion in Orchestration Playbooks

Included within `playbooks/workstation.yml` as part of the workstation system configuration:

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

In `local.yml`, hardware preflight checks detect graphical display capabilities before running desktop tasks:

```yaml
- name: Autonomous Workstation Provisioning
  hosts: localhost
  connection: local
  become: true
  roles:
    - role: desktop
      when: auto_enable_desktop | default(true) | bool
      tags: ["desktop", "system"]
```

### 3. Execution Commands

Run only desktop role tasks:

```bash
ansible-playbook playbooks/workstation.yml --tags "desktop"
```

Provision only system Flatpaks and Flathub:

```bash
ansible-playbook local.yml --tags "flathub,flatpaks"
```

Update Antigravity Hub and IDE binaries:

```bash
ansible-playbook local.yml --tags "antigravity"
```

---

## Verification & Health Checks

After role convergence, verify graphical workstation status:

### 1. Display Target & Session Verification

```bash
# Verify systemd default target
systemctl get-default
# Output should be: graphical.target

# Check display manager service status
systemctl status gdm.service
```

### 2. Flatpak & Flathub Verification

```bash
# Verify Flathub system remote
flatpak remotes --system

# List installed system Flatpaks
flatpak list --system --app
```

### 3. GNOME Shell Extensions Verification

```bash
# Verify enabled extensions for the active user
gsettings get org.gnome.shell enabled-extensions

# List active extensions via GNOME CLI
gnome-extensions list --enabled
```

### 4. Developer Tools Verification

```bash
# Verify VS Code installation
code --version

# Verify Antigravity desktop integration
ls -la /opt/antigravity /opt/antigravity-ide
desktop-file-validate /usr/share/applications/antigravity*.desktop

# Verify input-remapper daemon status
systemctl status input-remapper.service
```

---

## Testing & Linting

Verify role syntax and conventions using `ansible-lint`:

```bash
ansible-lint roles/desktop
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
