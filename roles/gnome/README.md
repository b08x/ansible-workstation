# Ansible Role: gnome

Provisions the GNOME desktop environment, GDM Wayland display manager, `graphical.target`, GNOME management Flatpaks, and GNOME Shell extensions across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

## Role Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `gnome_assert_enabled` | `bool` | `true` | Enable pre-flight environment, platform, and privilege assertions. |
| `gnome_flatpaks` | `list[str]` | `ExtensionManager`, `Refine` | System Flatpak applications to install for GNOME management. |
| `gnome_extensions` | `list[str]` | 9 `gnome-shell-extension-*` RPMs | System GNOME Shell extension RPM package names to install via DNF. |
| `gnome_user_extensions` | `list[str]` | 4 extension UUIDs | User GNOME Shell extension UUIDs to enable in dconf if present. |
| `gnome_extensions_enable` | `bool` | `false` | Control whether installed GNOME extensions are enabled in dconf. |

## Dependencies

None. Typically paired with `roles/theme` when `desktop_environment == 'gnome'`.
