# Ansible Role: sway

Standalone Sway Wayland window manager role for Fedora and Enterprise Linux workstations. Provisions the core Sway compositor, desktop companions (Waybar, Kanshi, Rofi-wayland, Mako), tools, greetd login manager with tuigreet, session environment variables, and user configuration following Fedora's layered architecture.

---

## Architecture & Layering

The `sway` role establishes the Wayland window management layer on the host workstation. It coordinates package installation, display manager handoff, session environment initialization, and modular user configuration.

```
+--------------------------------------------------------------------------+
|                     User Compositor Configuration                        |
|       ~/.config/sway/config (Layered include helper, mod, bindings)      |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Session Environment & Display Manager                |
|       /etc/sway/environment, ~/.config/sway/environment                  |
|       /etc/greetd/config.toml (tuigreet -> start-sway)                   |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Compositor Packages & Companions                     |
|       sway, swaybg, swayidle, swaylock, sway-systemd                     |
|       waybar, kanshi, rofi-wayland, mako, greetd, tuigreet               |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Host Operating System & Kernel                       |
|       Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10, systemd, DNF         |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as dispatcher routing to subtask files (`assert.yml`, `packages.yml`, `greetd.yml`, `environment.yml`, `config.yml`).
2. **Pre-flight Assertion Pattern**: `tasks/assert.yml` validates OS family (RedHat), platform versions, DNF package manager, effective root UID (`_sway_effective_uid`), and required user facts (`user.name`).
3. **Backup-on-Write Pattern**: All configuration files (`/etc/greetd/config.toml`, `/etc/sway/environment`, `~/.config/sway/environment`, `~/.config/sway/config`) set `backup: true`.
4. **Tag-as-Select Pattern**: Role tasks carry `sway` and granular tags (`packages`, `greetd`, `environment`, `config`, `assert`).
5. **Idempotency Overrides**: Supports `sway_force_install` and `sway_force_reconfigure` override variables.
6. **Private Fact Scoping**: Registered facts use private role prefix `_sway_*`.

---

## Requirements

- **Ansible Core**: `>= 2.14`
- **Target OS**: Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10, CentOS Stream 9/10.
- **Privileges**: Root access via `become: true` for packages, greetd, and `/etc/sway` deployment.
- **Variables**: Tier 1 host variable `user.name` and optional `user.home` must be defined.

---

## Role Variables

### Tier 1 Variables (Host / Global Scope)

| Variable | Type | Description |
|---|---|---|
| `user.name` | `string` | Primary workstation user account name. |
| `user.home` | `string` | Primary workstation user home directory (defaults to `/home/{{ user.name }}`). |
| `enable_desktop` | `bool` | Global toggle for desktop provisioning. |
| `desktop_ui_environment` | `string` | Desktop environment selector (`sway`, `gnome`, `cosmic`, `none`). |

### Tier 2 Variables (Role Defaults in `defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `sway_assert_enabled` | `true` | Gate execution of pre-flight assertion tasks. |
| `sway_force_install` | `false` | Force reinstall packages even if present. |
| `sway_force_reconfigure` | `false` | Force overwrite user config even if customized. |
| `sway_mod` | `"Mod4"` | Sway modifier key (`Mod4` = Super / Logo). |
| `sway_terminal` | `"foot"` | Default terminal emulator binary. |
| `sway_menu` | `"rofi -show drun"` | Application launcher command. |
| `sway_font` | `"pango:monospace 10"` | Font specification for window borders and UI. |
| `sway_install_companions` | `true` | Install Waybar, Kanshi, Rofi-wayland, Mako. |
| `sway_install_tools` | `true` | Install grim, slurp, wl-clipboard, etc. |
| `sway_install_greetd` | `true` | Install greetd and tuigreet packages. |
| `sway_manage_display_manager` | `true` | Configure greetd and disable conflicting display managers (GDM). |
| `sway_manage_environment` | `true` | Deploy session environment files. |
| `sway_greetd_command` | `"tuigreet --time --remember --remember-user-session --cmd sway"` | Greeter command for greetd. |
| `sway_greetd_user` | `"greetd"` | Daemon user for greetd. |
| `sway_greetd_vt` | `1` | Virtual terminal for greetd greeter. |
| `sway_environment_vars` | *(dict)* | Environment key-value mapping for Wayland sessions. |
| `sway_config_custom_includes` | *(list)* | Glob list for layered Sway configuration. |
| `sway_extra_config` | `""` | Extra configuration appended to `~/.config/sway/config`. |

---

## Example Playbook

```yaml
- name: Provision Sway Workstation
  hosts: workstations
  become: true
  roles:
    - role: sway
      when:
        - enable_desktop | default(true) | bool
        - desktop_ui_environment | default('none') == 'sway'
      tags: ["sway", "desktop", "system"]
```

---

## Tags

| Tag | Purpose |
|---|---|
| `sway` | Executes all tasks in the sway role. |
| `assert` | Executes pre-flight assertion validation. |
| `packages` | Installs compositor and companion RPM packages. |
| `greetd` | Configures greetd display manager and services. |
| `environment` | Configures Wayland session environment files. |
| `config` | Generates user Sway configuration and directories. |
