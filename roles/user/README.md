# User Role (`roles/user`)

Sets up the unprivileged workstation user environment, user directory layout, secondary group memberships, and user-space runtime tooling.

## Scope & Taxonomy

Under the [distribution taxonomy](../../docs/layering-architecture.md):
- **Ansible (`roles/user`)**: Manages the host user account, group memberships (`audio`, `video`, `render`, `input`), standard directory scaffolding (`~/.local/bin`, `~/Workspace`), and the system drop for `uv`.
- **Yadm**: Single owner of unprivileged dotfiles, shell rc configuration (`~/.zshrc`), language version managers (`rbenv`, `rustup`), default gems, and user Cargo crates (`bootstrap.d/20-cargo.sh`).
- **Decoupled**: Redundant Rustup installers, Cargo crate compilation loops, and `.zshrc` `lineinfile` modifications were eliminated from this role.

## Features

1. **User Account & Directories (`tasks/user.yml`, `tasks/directories.yml`)**:
   - Ensures the primary user exists with correct UID/GID and assigned shell.
   - Configures secondary group access for hardware acceleration, audio, and device input.
   - Creates directory structure (`~/.local/bin`, `~/Workspace`, `~/.config`).
2. **UV Python Tooling (`tasks/uv.yml`)**:
   - Installs official Astral `uv` binary to `$HOME/.local/bin/uv`.
   - Shell environment variables (such as `export UV_PYTHON_PREFERENCE="only-managed"`) are maintained in Yadm dotfile templates rather than Ansible inline mutations.

## Key Variables

| Variable | Default | Description |
|---|---|---|
| `user.name` | `b08x` | Primary workstation user account name |
| `user.group` | `b08x` | Primary group name |
| `user.home` | `/home/b08x` | Home directory path |
| `user.shell` | `/usr/bin/zsh` | Login shell path |
| `user.secondary_groups` | `"input,video,audio,render"` | Comma-separated secondary groups |
| `user_install_uv` | `true` | When true, installs the `uv` Python manager |
| `user_uv_version` | `"latest"` | Target version tag for `uv` |

## Tags

| Tag | Purpose |
|---|---|
| `user` | All tasks in the user role |
| `directories` | Directory structure creation |
| `uv` | UV installation tasks |
| `profile` | User account and shell verification |

## Example Usage

```yaml
- name: Setup workstation user environment
  hosts: workstations
  become: false
  roles:
    - role: user
      tags: ["user"]
```
