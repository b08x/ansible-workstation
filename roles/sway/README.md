# Ansible Role: sway

Standalone Sway Wayland window manager role for Fedora and Enterprise Linux workstations, featuring the **Aphelion Systems Engineering Theme** (adapted from `elenapan/dotfiles`). Provisions Sway / SwayFX, an interactive Eww widget suite with backend systems telemetry (containers, KVM, GPU/VRAM, host metrics), companion terminals (Foot, Kitty), Rofi-wayland launcher, Waybar fallback, greetd display manager, session environment variables, and modular user configuration.

---

## Architecture & Layering

The `sway` role establishes an opinionated, high-performance Wayland environment tailored for systems engineers. It coordinates repository enablement, package installation, display manager handoff, session lifecycle via `systemd --user`, and modular user configuration.

```
+--------------------------------------------------------------------------+
|                     User Compositor Configuration                        |
|       ~/.config/sway/config (Modular includes: 00-globals -> 10-autostart)|
|       ~/.config/sway/scripts/ (smart-split, move-to-edge, scratchpad)     |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Widgets, Theming & Companions                        |
|       Eww Widgets: bottom-bar, workspaces, powermenu, telemetry sidebar   |
|       Telemetry Daemons: containers (Podman/Docker), KVM, GPU/DRM, host  |
|       NetworkManager (nmcli), WirePlumber (wpctl)                        |
|       Terminals: Foot (foot.ini), Kitty (kitty.conf, colors.conf)        |
|       Launcher: Rofi-wayland (config.rasi, colors.rasi)                  |
|       Fallback Bar: Waybar (config, style.css)                           |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Session Lifecycle & Services                         |
|       ~/.config/systemd/user/ (eww.service, sway-telemetry.service)      |
|       Integrated with sway-session.target & graphical-session.target     |
|       /etc/greetd/config.toml (tuigreet -> start-sway)                   |
|       /etc/sway/environment, ~/.config/sway/environment                  |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Compositor Packages & Repositories                   |
|       COPR: copr:copr.fedorainfracloud.org:b08x:syncopated (Fedora)      |
|       Dual-track: SwayFX (rounded corners, shadows, blur) vs Sway        |
|       foot, kitty, eww, waybar, rofi-wayland, kanshi, mako, fonts        |
+--------------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                     Host Operating System & Kernel                       |
|       Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10, systemd, DNF         |
+--------------------------------------------------------------------------+
```

### Design Patterns Implemented

1. **Task Dispatcher Pattern**: `tasks/main.yml` acts as dispatcher routing to subtask files (`assert.yml`, `packages.yml`, `greetd.yml`, `environment.yml`, `config.yml`, `systemd.yml`).
2. **Pre-flight Assertion Pattern**: `tasks/assert.yml` validates OS family (RedHat), platform versions, DNF package manager, effective root UID (`_sway_effective_uid`), required user facts (`user.name`, `user.home`), valid `sway_bar_engine` (`eww`, `waybar`), and non-empty `sway_theme`.
3. **Backup-on-Write Pattern**: All configuration files (`/etc/greetd/config.toml`, `/etc/sway/environment`, `~/.config/sway/config`, `~/.config/sway/config.d/*.conf`, `~/.config/eww/*`, `~/.config/systemd/user/*.service`) set `backup: true`.
4. **Tag-as-Select Pattern**: Role tasks carry `sway` and granular tags (`packages`, `copr`, `greetd`, `environment`, `config`, `eww`, `apps`, `systemd`, `assert`).
5. **Idempotency Overrides**: Supports `sway_force_install` and `sway_force_reconfigure` override variables.
6. **Private Fact Scoping**: Registered facts use private role prefix `_sway_*`.

---

## Modular Configuration Structure

User Sway configurations are split into modular files under `~/.config/sway/config.d/`, included by `~/.config/sway/config`:

| File | Purpose |
|---|---|
| `00-globals.conf` | Modifiers, default applications (`$term`, `$menu`), and workspace definitions. |
| `01-colors.conf` | Aphelion color palette (`$xbg`, `$xfg`, `$x0`–`$x15`) and window decoration borders. |
| `02-appearance.conf` | Gaps (`inner 8`, `outer 4`), pixel borders (2px), and SwayFX effects (corner radius, blur, shadows). |
| `03-output.conf` | Wallpaper solid background and per-app max render times for responsive input. |
| `04-input.conf` | Keyboard options (`ctrl:nocaps`, repeat rates), touchpad tap/scroll, and pointer sensitivity. |
| `05-idle.conf` | Screen locking (300s) and display DPMS power off (600s) via `swayidle` and `swaylock`. |
| `06-modes.conf` | Modal controls for window resizing and moving containers to edges or workspaces. |
| `07-keys.conf` | Keybindings for tiling, smart splits, scratchpads, focus, and workspace switching. |
| `08-rules.conf` | Window rules for dialogs, scratchpads, floating volume/audio controls, and PiP. |
| `09-eww.conf` | Eww widget keybindings (sidebar, powermenu) and powermenu modal controls. |
| `10-autostart.conf` | Session initialization (DBus environment update) and bar engine dispatch (Eww vs Waybar). |

---

## Eww Widget Suite & Systems Engineering Telemetry

When `sway_use_eww: true` and `sway_bar_engine: "eww"`, the role installs and configures an Eww widget system styled with the Aphelion theme:

- **Bottom Dock Bar (`bottom-bar.yuck`)**: Minimalist status bar displaying active workspace buttons, current window title, clock, network status (`nmcli`), audio volume (`wpctl`), and toggle buttons.
- **Systems Telemetry Sidebar (`sidebar.yuck`)**: Slide-out pane dedicated to systems engineering observability:
  - **Containers**: Active Podman or Docker container counts and health status (`containers-status`).
  - **Virtual Machines**: Active KVM / libvirt domain counts via `virsh` (`kvm-status`).
  - **GPU & Acceleration**: GPU utilization and VRAM usage via `nvidia-smi` or DRM sysfs (`gpu-status`).
  - **Host Health**: 1/5/15 min load averages, RAM percentage, and failed systemd units (`system-metrics`).
- **Interactive Powermenu (`powermenu.yuck`)**: Overlay modal providing Lock (`swaylock`), Suspend, Reboot, and Power Off actions with escape key handling.
- **Fail-Safe Telemetry Daemons**: Telemetry scripts under `~/.config/eww/scripts/daemons/` return clean JSON and exit `0` even when virtualization, containers, or dedicated GPUs are absent.

---

## Theming & Application Integration

The Aphelion color palette (`#101319` background, `#f4f3ee` foreground, `#5294e2` blue accent, `#62c073` green, `#ea515d` red, `#ebcb8b` yellow) is applied consistently across:

- **Foot Terminal (`foot.ini`)**: Configured with JetBrains Mono, Font Awesome 6 Free, and Aphelion palette.
- **Kitty Terminal (`kitty.conf`, `colors.conf`)**: Configured with background opacity `0.95`, padding `8`, and Aphelion color table.
- **Rofi Launcher (`config.rasi`, `colors.rasi`)**: Fuzzy application launcher, run dialog, and window switcher.
- **Waybar Fallback (`config`, `style.css`)**: Aphelion-styled fallback bar for environments where Eww is disabled or on Enterprise Linux.

---

## systemd User Service Lifecycle

Session daemons are managed via `systemd --user` units linked to `sway-session.target` (provided by `sway-systemd`):

- `eww.service`: Launches `/usr/bin/eww daemon --no-daemonize` on login and reloads via `eww reload`.
- `sway-telemetry.service`: Runs the background systems telemetry polling daemon.

Units cleanly start when Sway initializes and terminate automatically upon session logout.

---

## Requirements

- **Ansible Core**: `>= 2.14`
- **Target OS**: Fedora 40+, AlmaLinux 9/10, Rocky Linux 9/10, CentOS Stream 9/10.
- **Privileges**: Root access via `become: true` for packages, greetd, and repository setup.
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
| `sway_copr_repositories` | `["copr:copr.fedorainfracloud.org:b08x:syncopated"]` | COPR repositories for SwayFX, Eww, and Wayland companion tools. |
| `sway_use_swayfx` | `true` | Install and configure SwayFX enhanced compositor instead of standard Sway. |
| `sway_use_eww` | `true` | Install and deploy Eww widget system. |
| `sway_bar_engine` | `"eww"` | Active bar engine (`eww` or `waybar`). |
| `sway_theme` | `"aphelion"` | Active desktop theme palette name. |
| `swayfx_blur` | `false` | Enable SwayFX background blur effect. |
| `swayfx_shadows` | `true` | Enable SwayFX drop shadows on windows and UI popups. |
| `swayfx_corner_radius` | `10` | Corner radius in pixels for rounded window corners. |
| `sway_install_companions` | `true` | Install Waybar, Kanshi, Rofi-wayland, Mako. |
| `sway_install_tools` | `true` | Install grim, slurp, wl-clipboard, pavucontrol, playerctl, etc. |
| `sway_install_greetd` | `true` | Install greetd and tuigreet packages. |
| `sway_manage_display_manager` | `true` | Configure greetd and disable conflicting display managers (GDM). |
| `sway_manage_environment` | `true` | Deploy session environment files. |
| `sway_greetd_command` | `"tuigreet --time --remember --remember-user-session --cmd sway"` | Greeter command for greetd. |
| `sway_greetd_user` | `"greetd"` | Daemon user for greetd. |
| `sway_greetd_vt` | `1` | Virtual terminal for greetd greeter. |
| `sway_environment_vars` | *(dict)* | Environment key-value mapping for Wayland sessions. |
| `sway_config_custom_includes` | `[]` | List of optional glob paths for custom Sway includes. |
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
| `copr` | Configures COPR repositories on Fedora targets. |
| `greetd` | Configures greetd display manager and services. |
| `environment` | Configures Wayland session environment files. |
| `config` | Generates user Sway configuration and directories. |
| `eww` | Configures Eww widgets, templates, and telemetry daemons. |
| `apps` | Deploys terminal (Foot, Kitty), Rofi, and Waybar configurations. |
| `systemd` | Deploys user session systemd services. |
