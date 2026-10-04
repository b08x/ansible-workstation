# Desktop Role (`roles/desktop`)

Provisions the graphical workstation environment, system-wide desktop integration tools, GNOME shell extensions, Antigravity IDE, and system-level Flatpaks on Fedora and Enterprise Linux.

## Scope & Taxonomy

Under the [distribution taxonomy](../../docs/layering-architecture.md):
- **Ansible (`roles/desktop`)**: Manages system-level desktop packages, display acceleration, system-wide GNOME extensions, Flathub system remote, and **system-management Flatpaks** (`ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy`).
- **Yadm (`80-install-user-flatpaks.sh`)**: Manages unprivileged **user-space desktop applications** (`Obsidian`, `Typora`, `Audacity`, `fre:ac`, `Helvum`, `Podman Desktop`, `DBeaver`).

## Features

1. **System Flatpaks (`tasks/flatpak.yml`)**:
   - Ensures the `flathub` system remote is present.
   - Installs system-scoped Flatpaks via `community.general.flatpak` (`method: system`).
2. **GNOME Desktop (`tasks/gnome.yml`, `tasks/gnome_extensions.yml`)**:
   - Installs system GNOME extensions (`dash-to-dock`, `appindicator`, `user-theme`, etc.).
   - Configures desktop themes and gsettings overrides.
3. **Developer Workstation Utilities**:
   - **VS Code**: Configures official Microsoft RPM repository and package.
   - **Antigravity Hub & IDE**: Downloads and extracts Google Antigravity Hub and IDE archives into system application paths.
   - **Input Remapper**: Installs and enables `input-remapper` daemon for hardware key rebinding.

## Key Variables

| Variable | Default | Description |
|---|---|---|
| `desktop_environment` | `gnome` | Desktop environment target (e.g. `gnome`) |
| `desktop_system_flatpaks` | *(4 packages)* | System management Flatpaks (`ExtensionManager`, `Flatseal`, `Warehouse`, `BoxBuddy`) |
| `desktop_antigravity_state` | `present` | State of Antigravity Hub and IDE installation |
| `desktop_antigravity_hub_url` | *(Google storage URL)* | Official tarball archive for Antigravity Hub |
| `desktop_antigravity_ide_url` | *(Google storage URL)* | Official tarball archive for Antigravity IDE |
| `desktop_gnome_extensions` | *(list)* | DNF system packages for GNOME extensions |
| `desktop_vscode_flatpak` | `false` | When true, installs VS Code via Flatpak instead of native RPM |

## Tags

| Tag | Purpose |
|---|---|
| `desktop` | All desktop provisioning tasks |
| `flatpaks` | Flathub remote and system Flatpak installations |
| `gnome` | GNOME packages, styling, and extension management |
| `antigravity` | Antigravity Hub and IDE installation |
| `vscode` | Visual Studio Code repository and package |
| `input-remapper` | Input remapper daemon and configuration |

## Example Usage

```yaml
- name: Configure desktop environment
  hosts: localhost
  become: true
  roles:
    - role: desktop
      tags: ["desktop"]
```
