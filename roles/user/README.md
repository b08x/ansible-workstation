# User Role (`roles/user`)

Installs user-space Python runtimes via `uv` and carries dormant firstboot onboarding scripts relocated from the former `desktop` role. The role is deliberately small — most of what you might expect a "user" role to do (account creation, group membership, directory scaffolding) lives elsewhere, and this document says where.

## Scope & Taxonomy

Under the [distribution taxonomy](../../docs/layering-architecture.md):

- **Ansible (`roles/user`)**: Installs a managed Python runtime version into the user's environment via `uv python install`. The role runs unprivileged (`become: false`) and assumes `uv` is already on `PATH`.
- **Yadm**: Single owner of unprivileged dotfiles, shell rc configuration (`~/.zshrc`), language version managers (`rbenv`, `rustup`), default gems, and user Cargo crates (`bootstrap.d/20-cargo.sh`).
- **User identity**: The primary user account (`user.name`, `user.group`, `user.home`, `user.shell`, `user.secondary_groups`) is defined as Tier 1 host/domain variables in `inventory/group_vars/all.yml` — not created or mutated by this role.
- **Decoupled**: Redundant Rustup installers, Cargo crate compilation loops, and `.zshrc` `lineinfile` modifications were eliminated from this role.

## Features

1. **Pre-flight Assertions (`tasks/assert.yml`)**:
   - Validates that Ansible facts are gathered, the host is a supported RedHat-family distribution (Fedora, AlmaLinux, Rocky, RedHat, CentOS), the Tier 1 `user.name` variable is defined, `user.home` is an absolute path when set, and `user_uv_python_version` is non-empty.
   - Gated by `user_assert_enabled` (default: `true`); tagged `assert` and `always`.

2. **UV Python Runtime (`tasks/uv.yml`)**:
   - Runs `uv python install {{ user_uv_python_version }}` (default: `3.12`) as the unprivileged user.
   - The `uv` binary itself is expected to be on `PATH` — installed outside this role. (The former `roles/base` carried `uv` in its Fedora package list, but the migration to `roles/common` in commit `0b73d61` curated the package list down to a terminal baseline and dropped it; no role currently installs `uv`. If you need `uv` installed by Ansible, that gap needs to be filled — likely in `roles/common` or `roles/tools`.)
   - Shell environment variables (such as `export UV_PYTHON_PREFERENCE="only-managed"`) are maintained in Yadm dotfile templates rather than Ansible inline mutations.

3. **Firstboot Onboarding (`tasks/firstboot.yml`, `files/firstboot/`)** — *dormant*:
   - Standalone firstboot onboarding scripts and autostart launchers moved from the former `desktop` role in commit `d72b8a8`.
   - Installs `/usr/local/bin/syncopated-firstboot`, a terminal launcher, a desktop autostart entry (`/etc/xdg/autostart/`), and a `profile.d` login hook.
   - **Not included by `tasks/main.yml`** — preserved for future onboarding workflows.

4. **Dormant task files (`tasks/pip.yml`, `tasks/ranger.yml`)** — *commented out*:
   - `pip.yml` would enforce `require-virtualenv` in the user's pip config.
   - `ranger.yml` would install the Ranger file manager (system package, falling back to `pipx`).
   - Both are commented out in `tasks/main.yml` and carry no effect until re-enabled.

## Key Variables

### Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `user_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`) to fail fast on invalid environments |
| `user_uv_python_version` | `3.12` | Python version to install in user space via `uv python install` |

### Tier 1 Host/Domain Variables (from `inventory/group_vars/all.yml`)

These are not role defaults — they are expected to be supplied by inventory, `group_vars`, or `host_vars`:

| Variable | Example | Description |
|---|---|---|
| `user.name` | `b08x` | Primary workstation user account name |
| `user.group` | `b08x` | Primary group name |
| `user.home` | `/home/b08x` | Home directory path |
| `user.shell` | `/usr/bin/zsh` | Login shell path |
| `user.secondary_groups` | `"wheel,input,video,audio,render"` | Comma-separated secondary groups |

## Tags

| Tag | Purpose | Active? |
|---|---|---|
| `user` | All tasks in the user role | Yes |
| `assert` | Pre-flight requirement assertion tasks | Yes |
| `always` | Tasks that run regardless of tag selection | Yes |
| `distro` | Distribution variable loading | Yes |
| `uv` | UV Python installation tasks | Yes |
| `firstboot` | Firstboot onboarding scripts | No — not included by `main.yml` |
| `pip` | Pip configuration (require-virtualenv) | No — commented out in `main.yml` |
| `ranger` | Ranger file manager installation | No — commented out in `main.yml` |

## Example Usage

```yaml
- name: Setup workstation user environment
  hosts: workstations
  become: false
  roles:
    - role: user
      tags: ["user"]
```
