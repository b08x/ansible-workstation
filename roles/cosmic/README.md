# Ansible Role: cosmic

Provisions the COSMIC desktop environment, Qt6 `cutecosmic` integration, `/etc/skel/.config/cosmic` defaults, and display manager selection (`cosmic-greeter` or `gdm`) on Fedora 43+ and Enterprise Linux 10+.

## Role Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `cosmic_assert_enabled` | `bool` | `true` | Enable pre-flight environment, platform, and privilege assertions. |
| `cosmic_display_manager` | `str` | `"cosmic-greeter"` | Target display manager for COSMIC desktop (`cosmic-greeter` or `gdm`). |
| `cosmic_use_copr` | `bool` | `false` | Enable `ryanabx/cosmic-epoch` COPR repository on Fedora before installing packages. |
| `cosmic_install_supplementary_apps` | `bool` | `false` | Install supplementary COSMIC desktop applications (`@cosmic-desktop-apps`). |

## Dependencies

None. Typically paired with `roles/theme` when `desktop_environment == 'cosmic'`.
