# User Role (`roles/user`)

Installs and manages the **user-space developer toolchains and extension lists** for the workstation user: the uv-managed Python runtime, the Bun JS/TS runtime, the Go toolchain (system-first with a user tarball fallback), the Rust/cargo toolchain and crate set, GNOME Shell extensions, and VS Code extensions. The role executes in the workstation user's context (`become: true`, `become_user: "{{ user.name }}"`), guaranteeing unprivileged execution as the target workstation user even when `ansible-pull` or `ansible-playbook` is invoked with `--become` / `-K`. System package manager fallbacks inside the Go and cargo decision trees explicitly escalate to `become_user: root`.

**Migration note (2026-11):** the task surface migrated from yadm `bootstrap.d` (behavior parity) and absorbed the divested CLI toolchains of [`roles/tools`](../tools/README.md): `bun` (now `~/.bun/bin`, user space), the Go toolchain, cargo/crates, GNOME Shell extensions, and VS Code extensions all live here now. `homebrew` was dropped entirely — no role installs it. `inxi` and `gitflow-avh` moved to [`roles/common`](../common/README.md), and the VS Code **binary** remains in [`roles/tools`](../tools/README.md) as a real opt-in (`tools_install_vscode` defaults to `false`).

## Scope & Taxonomy

Under the [distribution taxonomy](../../docs/layering-architecture.md):

- **Ansible (`roles/user`)**: unprivileged, user-space binaries and extension lists — `~/.bun/bin/bun`, `~/.local/go` (with `~/.local/bin/go` + `gofmt` symlinks), `~/.cargo` (rustup or system cargo), `~/.local/share/gnome-shell/extensions`, and VS Code extension sets. Ansible never writes shell rc files or `~/.cargo/config.toml`.
- **Yadm (Layer 2)**: single owner of dotfiles, shell rc files (`~/.zshenv` sources `~/.cargo/env`; `~/.zshrc` owns PATH additions), API keys, and the yadm `bootstrap.d` scripts (which remain the bootstrap-time fallback for the migrated behaviors).
- **User identity**: the primary user account (`user.name`, `user.group`, `user.home`, `user.shell`, `user.secondary_groups`) is defined as Tier 1 host/domain variables in `inventory/group_vars/all.yml` — not created or mutated by this role. `user.home | default('/home/' ~ user.name)` is the lazy Tier 1 consumption idiom.

## Task Surface (`tasks/main.yml` dispatcher)

Every include is gated by `user_<feature> | default(bool) | bool` and tagged `[<feature>, "user"]`:

| Task file | Gate (default) | Purpose |
|---|---|---|
| `assert.yml` | `user_assert_enabled` (`true`) | Pre-flight fail-fast assertions (facts, platform, identity, manifest shapes, runs-as-expected-user) |
| `uv.yml` | `user_install_uv` (`true`) | `uv python install {{ user_uv_python_version }}` (the `uv` binary is expected on PATH, installed outside this role) |
| `bun.yml` | `user_install_bun` (`true`) | User-space Bun runtime at `user_bun_dest` (`~/.bun/bin/bun`); skip-if-present guard + `user_bun_force_install` |
| `go.yml` | `user_install_go` (`true`) | **Go decision tree**: probe `/usr/bin/go` → DNF `golang` fallback (single escalation) → user-space tarball to `~/.local/go` with `~/.local/bin` symlinks when the system go is absent or older than `user_go_min_version`; `user_go_force_install` bypasses the system check; a final assert pins the effective `go` to the minimum |
| `cargo.yml` | `user_install_cargo` (`true`) | **Rust decision tree**: probe `/usr/bin/cargo` (never via PATH) → DNF `cargo` fallback (single escalation) vs `user_cargo_min_system_version` → rustup (`--no-modify-path`, skip-if-present) → DNF-preferred crates via `user_cargo_crate_dnf_map` with `cargo install --locked` fallback per crate; `user_cargo_force_install` forces rustup, `user_cargo_force_crates` forces per-crate re-attempt; TMPDIR noexec handling via `~/.cargo/tmp` |
| `gnome-extensions.yml` | `user_install_gnome_extensions` (`{{ enable_desktop \| default(false) \| bool }}`) | Installs the configured UUID set from `user_gnome_extensions_base_url` (extensions.gnome.org) via `gnome-extensions install --force`; non-fatal per-UUID failures; monotonic-union dconf enable (never disables); `user_gnome_extensions_force_install` forces re-install |
| `vscode-extensions.yml` | `user_install_vscode_extensions` (`true`) | CLI resolution (`user_vscode_command` → native `code` → the `com.visualstudio.code` Flatpak) → case-normalized `--list-extensions` diff → non-fatal installs; `user_vscode_force_install` forces re-install |

Notes:

- The dispatcher opens with a `Starting user tasks` debug tagged `["user", "always"]`, includes `assert.yml` first, and loads `vars/{{ ansible_distribution }}.yml` via an include tagged `["user", "distro"]`.
- The VS Code **binary** is not installed here — [`roles/tools`](../tools/README.md) owns it as a real opt-in (`tools_install_vscode: false`). This task file only manages the extension list against whatever CLI is resolvable.
- Per-item resilience idiom: looped installs use `failed_when: false` with a follow-up per-failure debug report; group-level `block/rescue` prints the human-readable failure (blocks are not loopable, so the two layers are complementary).
- `set_fact` strategy/decision split: a `set_fact` evaluates all keys up-front, so consumers of `_user_go_strategy` / `_user_cargo_strategy` live in a later task than the one that defines them ([failure point 17](../../docs/failure-points.md) — lazy evaluation).

## Key Variables

### Tier 2: Role Defaults (`defaults/main.yml`)

| Variable | Default | Description |
|---|---|---|
| `user_assert_enabled` | `true` | Gate pre-flight assertions (`tasks/assert.yml`) |
| `user_uv_python_version` | `"3.12"` | Python version installed via uv (Tier 1 override `user_uv_python_version` lives in `group_vars/all.yml`) |
| `user_install_uv` | `true` | Gate `uv python install` |
| `user_install_bun` | `true` | Gate user-space Bun installation |
| `user_bun_dest` | `{{ user.home \| default('/home/' ~ user.name) }}/.bun/bin/bun` | Bun binary destination |
| `user_bun_url` | `https://github.com/oven-sh/bun/releases/latest/download/bun-linux-x64.zip` | Bun release archive URL |
| `user_bun_force_install` | `false` | Skip-if-present override for bun |
| `user_install_go` | `true` | Gate the Go decision tree |
| `user_go_min_version` | `"1.22"` | Minimum acceptable effective Go version |
| `user_go_version` | `"1.27.1"` | User-space Go tarball version |
| `user_go_url` | `https://go.dev/dl/go{{ user_go_version }}.linux-{{ arm64/amd64 }}.tar.gz` | Go tarball URL (arch from `ansible_architecture`) |
| `user_go_dest_dir` | `{{ user.home \| default(...) }}/.local/go` | User-space Go tree (go/gofmt symlinked into `~/.local/bin`) |
| `user_go_force_install` | `false` | Force the user-space Go (re)install |
| `user_install_cargo` | `true` | Gate the cargo/Rust decision tree |
| `user_cargo_force_install` | `false` | Force the rustup toolchain install |
| `user_cargo_force_crates` | `[]` | Crates always re-attempted despite presence |
| `user_cargo_rustup_url` | `https://sh.rustup.rs` | rustup installer URL |
| `user_cargo_min_system_version` | `"1.80"` | Minimum acceptable SYSTEM cargo (`/usr/bin/cargo`) version |
| `user_cargo_crates` | 10-entry list (from yadm `cargo-packages.txt`) | Crate manifest to provision |
| `user_cargo_crate_bin_map` | `bottom: btm`, `ripgrep_all: rga`, `dua-cli: dua`, `du-dust: dust` | Crate → binary name for skip-if-present probes |
| `user_cargo_crate_dnf_map` | `dua-cli`, `gitui`, `eza` | Crate → DNF package (DNF-preferred install) |
| `user_install_gnome_extensions` | `{{ enable_desktop \| default(false) \| bool }}` | Lazy Tier 1 consumption — only managed on desktops |
| `user_gnome_extensions` | 4 UUID list (from yadm `gnome-extensions.txt`) | GNOME Shell extension manifest |
| `user_gnome_extensions_force_install` | `false` | Force extension re-installation |
| `user_gnome_extensions_base_url` | `https://extensions.gnome.org` | Metadata/bundle base URL |
| `user_install_vscode_extensions` | `true` | Gate VS Code extension management |
| `user_vscode_command` | `""` | Optional CLI override (argv string); empty = auto-detect |
| `user_vscode_force_install` | `false` | Force extension re-installation |
| `user_vscode_extensions` | 68-entry list (from yadm `vscode-extensions.txt`) | Marketplace extension manifest |

### Tier 1 Host/Domain Variables (from `inventory/group_vars/*.yml`)

Not role defaults — supplied by inventory:

| Variable | Example | Description |
|---|---|---|
| `user.name` | `b08x` | Primary workstation user account name |
| `user.home` | `/home/b08x` | Home directory path (absorbed lazily via `user.home \| default('/home/' ~ user.name)`) |
| `user.group`, `user.shell`, `user.uid`, `user.secondary_groups` | — | Identity facts consumed by `assert.yml` |
| `enable_desktop` | `true` | Lazily consumed by `user_install_gnome_extensions` |
| `user_uv_python_version` | `"3.14"` | Tier 1 override of the role default Python version |

### Registered variables

All registrations use the `_user_*` prefix (`_user_bun_stat`, `_user_go_strategy`, `_user_cargo_home`, `_user_gnome_install_targets`, `_user_vscode_targets`, …).

## Tags

| Tag | Purpose |
|---|---|
| `user` | All tasks in the user role |
| `assert` / `always` | Pre-flight assertion tasks |
| `distro` | Distribution variable loading |
| `uv` | uv Python runtime |
| `bun` | User-space Bun runtime |
| `go` | Go decision tree |
| `cargo` | Rust/cargo decision tree and crates |
| `gnome-extensions` | GNOME Shell extension management |
| `vscode-extensions` | VS Code extension management |

## Layer Boundary & Escalation Notes

- The role writes **no shell rc files** and no `~/.cargo/config.toml` — PATH coverage comes from Tier 1 `workstation_path_dirs` (`group_vars/all.yml`) and Layer 2 dotfiles.
- Exactly two privilege escalations to root exist, both `become: true` with `become_user: root` on DNF tasks inside decision trees: the Go tree's `dnf golang` fallback and the cargo tree's DNF fallbacks (`cargo` package and DNF-preferred crate packages). All other tasks run as the unprivileged workstation user.
- Skip-if-present guards pair with `*_force_install` overrides: `user_bun_force_install`, `user_go_force_install`, `user_cargo_force_install` (rustup) + `user_cargo_force_crates` (per crate), `user_gnome_extensions_force_install`, `user_vscode_force_install`.
- Check-mode safety: mutating blocks skip under `ansible_check_mode`; probes run with `check_mode: false`.

## Example Usage

```yaml
- name: User Workstation Setup
  hosts: workstations
  become: true
  become_user: "{{ user.name }}"
  roles:
    - role: user
      tags: ["user", "system", "assert"]
```

Running a single feature:

```bash
ansible-playbook playbooks/workstation.yml --tags "bun,go"
```
