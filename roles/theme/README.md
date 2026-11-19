# Ansible Role: theme

Provisions Qt5/Qt6 and GTK3/GTK4 runtime toolkit packages and the Yaru system desktop theme across Fedora and Enterprise Linux (AlmaLinux, Rocky Linux).

## Role Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `theme_assert_enabled` | `bool` | `true` | Enable pre-flight environment, platform, and privilege assertions. |
| `theme_install_toolkits` | `bool` | `true` | Install Qt5/Qt6 and GTK3/GTK4 runtime toolkit packages. |
| `theme_name` | `str` | `'yaru'` when `desktop_environment == 'gnome'`, else `'none'` | System desktop theme to install (`yaru` or `none`). |
| `theme_force_install` | `bool` | `false` | Force reinstallation or rebuild of Yaru theme even when `/usr/share/themes/Yaru` exists. |

## Dependencies

None. Uses Tier 1 `desktop_environment` to determine the default `theme_name`.
