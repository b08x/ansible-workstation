# Ansible Role: desktop_ui

Provisions the graphical workstation environment, display server libraries, desktop environment dispatch (GNOME, COSMIC, Sway), system-wide GNOME shell extensions, display manager configuration, and the Yaru desktop theme suite across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

---

## Overview & Architecture

Under the [workstation layering taxonomy](../../docs/layering-architecture.md), the `desktop_ui` role operates at **Layer 1 (Ansible Machine Orchestration)** to provision the graphical display environment and core window management infrastructure. User applications, IDEs, and developer tools reside in [`roles/tools`](../tools) and user-space dotfiles (**Layer 2: Yadm**).

```
+--------------------------------------------------------------------------+
|                       Layer 2: Yadm (User Space)                         |
|   Unprivileged User Desktop Apps (~/bootstrap.d/80-install-user-flatpaks.sh):|
|   Obsidian, Typora, Audacity, fre:ac, Helvum, Podman Desktop, DBeaver    |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                   Layer 1: roles/desktop_ui (Ansible)                    |
|   - Display Toolkits: Qt5/Qt6 & GTK3/GTK4 Runtime Libraries              |
|   - Environment Dispatch: GNOME (active), COSMIC (stub), Sway (stub)     |
|   - GNOME Stack: GNOME Core, GDM & graphical.target                      |
|   - GNOME Extensions: DNF System Packages & dconf State Management        |
|   - Themes: Yaru Theme Suite (DNF on Fedora; Meson/Ninja Source on EL)   |
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

1. **Task Dispatcher Pattern**: [`tasks/main.yml`](tasks/main.yml) acts as the primary dispatcher. After pre-flight assertions and toolkit packages are installed, it dynamically includes `tasks/{{ desktop_ui_environment }}/main.yml`.
2. **Environment Dispatch & Modular Stubs**:
   - `gnome`: Fully implemented under `tasks/gnome/` (`gnome.yml`, `extensions.yml`, `theme.yml`).
   - `cosmic`: Stub (`tasks/cosmic/main.yml`) providing the extension slot for future COSMIC desktop environment integration.
   - `sway`: Stub (`tasks/sway/main.yml`) providing the extension slot for future Sway window manager provisioning.
3. **Distro-Switching Pattern (Dialect A)**: Dynamic OS-specific variable inclusion via `vars/{{ ansible_distribution }}.yml`, defining distribution packages (`desktop_ui_packages.qt`, `gtk`, `gnome`, `theme`) cleanly without inline conditional blocks.
4. **Failure-Shape Pattern (Shape 1: Context Re-raise)**:
   - [`tasks/gnome/theme.yml`](tasks/gnome/theme.yml): Catches failures in both Fedora DNF installation and Enterprise Linux source builds (meson/ninja), outputs diagnostic repository/compilation context, and cleanly halts execution via `ansible.builtin.fail`.
5. **Tag-as-Select Pattern**: Every task include and block is tagged with the primary `desktop_ui` tag and fine-grained feature tags (`gnome`, `cosmic`, `sway`, `theme`, `extensions`, `packages`). Playbook entry points maintain the `desktop` alias tag for backward compatibility.
6. **Handler Notification Pattern**: Changes to display manager configuration (`/etc/gdm/custom.conf`) notify `Restart GDM`.
7. **User Context Isolation (`become_user`)**: User-scoped configurations (GNOME extension dconf state) execute directly under `become_user: "{{ user.name }}"` to ensure appropriate permissions in user schemas.
8. **Pre-flight Assertion Pattern**: Frontloads system requirement verification ([`tasks/assert.yml`](tasks/assert.yml)) to fail fast when prerequisites (OS family, DNF package manager, effective root privileges, desktop environment in `['gnome', 'cosmic', 'sway']`) are not met.
9. **Check-Mode Safety Pattern**: Read-only command probes ([`systemctl get-default`](tasks/gnome/gnome.yml) and [`gsettings get`](tasks/gnome/extensions.yml)) specify `check_mode: false` so that runtime facts and target state are accurately discovered during dry runs without emitting false change events.
10. **Strict List Typing Pattern**: Conditional package installations and list length checks utilize explicit `| default([]) | length > 0` evaluations rather than bare list truthiness, enforcing strict typing compliance under Ansible-core 2.18+.

---

## Core Components & Subsystems

### 1. Display Toolkits & Graphical Server ([`tasks/main.yml`](tasks/main.yml), [`tasks/gnome/gnome.yml`](tasks/gnome/gnome.yml))
- Deploys Qt runtime libraries (`qt5`, `qt6`, `qt5ct`, `qt6ct`, `qscintilla-qt5`) and GTK libraries (`gtk4`, `gtk3-devel`, `gtksourceview4`, `gtksourceview5`).
- On GNOME hosts (`desktop_ui_environment == 'gnome'`), installs the GNOME desktop environment package groups and tools (`@gnome-desktop`, `gdm`, `gnome-shell`, `gnome-session-wayland-session`, and `gnome-tweaks`).
- Configures GDM for native Wayland display server operation (`WaylandEnable=true` under `[daemon]` in `/etc/gdm/custom.conf`).
- Inspects systemd default target (`systemctl get-default` executed with `check_mode: false`) and promotes to `graphical.target` when not already set.
- Ensures `gdm.service` is enabled and started on systemd targets.

### 2. GNOME Shell Extensions ([`tasks/gnome/extensions.yml`](tasks/gnome/extensions.yml))
- Provisions system GNOME shell extension RPM packages via DNF (`desktop_ui_gnome_extensions`).
- By default, extensions are left disabled (`desktop_ui_gnome_extensions_enable: false`).
- When `desktop_ui_gnome_extensions_enable` is set to `true`, enables configured extensions in dconf for the target user.

### 3. Desktop Theming ([`tasks/gnome/theme.yml`](tasks/gnome/theme.yml))
- Checks `/usr/share/themes/Yaru` directory via `ansible.builtin.stat` to skip redundant installation or source builds when the theme is already present.
- Supports forcing re-installation/re-build via `desktop_ui_theme_force_install: true`.
- **Fedora**: Installs the Ubuntu Yaru theme family from DNF packages (`yaru-theme`, `gnome-shell-theme-yaru`, `yaru-gtk3-theme`, `yaru-gtk4-theme`, `yaru-gtksourceview-theme`, `yaru-icon-theme`, `yaru-sound-theme`). Note that `yaru-gtk2-theme` is retired on Fedora 44 and dynamically filtered out via `desktop_ui_packages.theme | reject('equalto', 'yaru-gtk2-theme') | list`.
- **Enterprise Linux (AlmaLinux & Rocky Linux)**: Installs build dependencies, clones the upstream Yaru theme repository, and compiles/installs system-wide via `meson setup build` and `ninja -C build install`.

### 4. COSMIC & Sway Stubs ([`tasks/cosmic/main.yml`](tasks/cosmic/main.yml), [`tasks/sway/main.yml`](tasks/sway/main.yml))
- Extension slots for future desktop environments.
- Selecting `desktop_ui_environment: cosmic` or `desktop_ui_environment: sway` executes an informational message and performs no host mutations.

---

## Role Variables

### Tier 1: Host & Domain Scope Variables

These variables represent machine hardware, system capabilities, or user identity (SSOT) defined in `group_vars/` or `host_vars/`:

| Variable | Default | Description |
|---|---|---|
| `user.name` | `ansible_user_id` | Primary workstation user account name (SSOT) used for dconf and user-level tools. |
| `enable_desktop` | `true` | System-wide flag in `group_vars/` enabling graphical workstation provisioning. |
| `auto_enable_desktop` | `true` | Capability flag evaluated during `local.yml` preflight checks to determine whether to include the desktop_ui role on graphical systems (`pull_enable_desktop \| default(enable_desktop \| default(true))`). |

### Tier 2: Role Defaults (`defaults/main.yml`)

These variables are namespaced with `desktop_ui_*` and control role-specific behavior:

| Variable | Default | Description |
|---|---|---|
| `desktop_ui_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`) to fail fast on invalid environments. |
| `desktop_ui_environment` | `"gnome"` | Target desktop environment (`gnome`, `cosmic`, or `sway`). |
| `desktop_ui_display_manager` | `"gdm"` | Target display manager placeholder (default `gdm`). |
| `desktop_ui_theme_force_install` | `false` | When true, forces theme installation/build even if `/usr/share/themes/Yaru` is present. |
| `desktop_ui_gnome_extensions` | *(list)* | DNF system package names for GNOME shell extensions. |
| `desktop_ui_gnome_user_extensions` | *(list)* | Extension UUIDs for user extensions installed in `~/.local/share/gnome-shell/extensions`. |
| `desktop_ui_gnome_extensions_enable` | `false` | When true, enables configured extensions in dconf. Disabled by default. |

### Tier 2: Distribution Variables (`vars/*.yml`)

Loaded dynamically from `vars/{{ ansible_distribution }}.yml`:

| Variable | Type | Description |
|---|---|---|
| `desktop_ui_packages.qt` | `list` | Distribution-specific Qt5 and Qt6 runtime packages. |
| `desktop_ui_packages.gtk` | `list` | Distribution-specific GTK3 and GTK4 packages. |
| `desktop_ui_packages.gnome` | `list` | Distribution package groups and tools for GNOME desktop. |
| `desktop_ui_packages.theme` | `list` | Theme packages on Fedora; build dependencies on Enterprise Linux. |

---

## Handlers

| Handler Name | Description |
|---|---|
| `Restart GDM` | Queries active seat sessions via `loginctl`. If no active local sessions are found, restarts `gdm.service`. If user sessions are active, displays a non-blocking Zenity desktop notice informing the user that display manager configuration changed. |

*(Note: `Daemon reload` handler is owned by [`roles/tools`](../tools) which manages input-remapper service definitions).*

---

## Tags

Use tags with `--tags` or `--skip-tags` for targeted execution:

| Tag | Scope | Description |
|---|---|---|
| `desktop_ui` | Role | Applies to all tasks within the `desktop_ui` role. |
| `desktop` | Alias | Backward-compatible alias tag on playbook role entries. |
| `assert` | Validation | Executes pre-flight assertion tasks to validate system requirements and privileges. |
| `packages` | Feature | Targets Qt, GTK, and GNOME DNF package installation. |
| `gnome` | Feature | Executes GNOME desktop configuration and display target promotion. |
| `cosmic` | Feature | Executes COSMIC environment dispatch. |
| `sway` | Feature | Executes Sway environment dispatch. |
| `extensions` | Feature | Manages GNOME Shell extensions installation and dconf enablement. |
| `theme` | Feature | Provisions Yaru desktop and shell themes (DNF or source build). |
| `always` | System | Preamble debug statements and OS variable inclusion. |

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
    - role: networking
      tags: ["networking", "system"]
    - role: containerd
      tags: ["containerd", "virt"]
    - role: desktop_ui
      tags: ["desktop_ui", "desktop", "system"]
    - role: libvirt
      tags: ["libvirt", "virt"]
```

### 2. Autonomous Local Provisioning (`local.yml`)

```yaml
    - name: Execute desktop_ui role
      ansible.builtin.include_role:
        name: desktop_ui
      when: auto_enable_desktop | default(false) | bool
      tags: ["desktop_ui", "desktop", "system", "assert"]
```

---

## Testing & Linting

Verify role syntax and conventions using `ansible-lint`:

```bash
ansible-lint roles/desktop_ui
```

---

## License

GPL-3.0-or-later

## Author Information

Syncopated Workstation Team
