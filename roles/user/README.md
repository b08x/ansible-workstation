# 👤 User Role (`roles/user`)

Under the [distribution taxonomy](../../docs/layering-architecture.md), this role provisions the unprivileged developer toolchain of one workstation account: the uv-managed Python runtime, the Bun JS/TS runtime, a system-first Go toolchain with a user-space fallback, the Rust/cargo toolchain with a 10-crate manifest, 4 GNOME Shell extensions, and an opt-in 68-entry VS Code extension list.

Every dispatched task runs as the workstation user via `apply: become: true, become_user: "{{ user.name }}"`, so the role stays unprivileged even under `--become` / `-K`; the only exceptions are three bounded root DNF sites in the Go and cargo decision trees and the root-context firstboot include (`become: true, become_user: root`: system-path deploys plus the machine marker write — see Layer Boundary & Escalation). The user play runs after the system plays converge (`playbooks/workstation.yml:79-85`, mirroring `local.yml`), so user-space toolchains build against freshly provisioned system packages.

> **Provenance.** Every fact in this README — gates, defaults, URLs, version strings, list lengths, escalation sites — was verified against the codebase at commit `ccfade8`. Anchors are file-level unless the fact itself is a location; the three root DNF sites, the root-context firstboot include, and the two playbook invocations carry line-level anchors as evidence.

## 📜 Migration History (2026-11)

**From yadm `bootstrap.d` — migration complete.** This task surface migrated from the yadm bootstrap scripts with behavior parity. The seed manifests (`cargo-packages.txt`, `gnome-extensions.txt`, `vscode-extensions.txt`) no longer exist in the yadm tree, so the values in `defaults/main.yml` are now the live manifests. The bootstrap-time fallback no longer exists either: `bootstrap.d/` now contains only `01-ruby.sh`, `02-ansible-pull.sh`, `03-zsh.sh`, `80-install-user-flatpaks.sh`, `85-rubymine.sh`, and `90-obsidian-flatpak-setup.sh`.

**From [`roles/tools`](../tools/README.md).** This role absorbed the divested CLI toolchains: Bun (now `~/.bun/bin/bun`, user space), the Go toolchain, cargo and its crates, GNOME Shell extensions, and VS Code extension management. Homebrew was dropped entirely; no role installs it. `inxi` and `gitflow-avh` moved to [`roles/common`](../common/README.md). The VS Code _binary_ remains in [`roles/tools`](../tools/README.md) as a real opt-in (`tools_install_vscode: false`); this role only manages extensions, and only when its opt-in gate is enabled.

## 🗺️ Overview & Architecture

The role runs at Layer 1 (Ansible machine orchestration) but installs strictly into user space, keeping a three-way ownership boundary: Ansible owns unprivileged binaries and extension lists; Yadm (Layer 2) owns dotfiles, shell rc files, and API keys; Tier 1 inventory owns identity and the PATH contract.

```
+--------------------------------------------------------------------------+
|                      Layer 2: Yadm (User Space)                          |
|         Dotfiles, shell rc files, API keys, ~/.cargo/config.toml         |
|   Read-only for this role: no rc writes; rustup runs --no-modify-path     |
+--------------------------------------------------------------------------+
                                   |
                                   | Tier 1 contract: user.name, user.home,
                                   | desktop_environment, workstation_path_dirs
                                   v
+--------------------------------------------------------------------------+
|             Layer 1: roles/user — tasks/main.yml dispatcher              |
|     every include applies become: true, become_user: "{{ user.name }}"    |
|   assert · uv · bun · go · cargo · gnome-extensions · vscode-extensions   |
|     · firstboot                                                          |
|     (8 gated includes; 7 run by default on this desktop inventory —      |
|      VS Code extensions are the single opt-in `false` gate)               |
|   go.yml / cargo.yml decision trees: probe /usr/bin/{go,cargo},          |
|    prefer the system package, fall back to ~/.local/go or rustup          |
+--------------------------------------------------------------------------+
                                   |
                                   | exactly 3 bounded root DNF sites
                                   v
+--------------------------------------------------------------------------+
|            Layer 0: System packages via DNF (become_user: root)          |
|    golang (go.yml) · cargo (cargo.yml) · dua-cli/gitui/eza (crate loop)   |
+--------------------------------------------------------------------------+
```

### 📐 Design Patterns

1. **Task dispatcher** — `tasks/main.yml` routes to eight includes, each gated by `user_<feature> | default(...) | bool` and tagged `[<feature>, "user"]` (the firstboot include is the dispatcher's only root-context entry).
2. **Fail-fast assertions** — `assert.yml` validates platform, identity, and manifest shapes before any mutation.
3. **Lazy Tier 1 consumption** — `user_install_gnome_extensions` derives its gate from `desktop_environment == 'gnome'`.
4. **Skip-if-present + force overrides** — the installers probe before installing — `uv` is the exception, running `uv python install` unconditionally — and a matching `*_force_install` (or `user_cargo_force_crates`) bypasses the probe.
5. **Per-item resilience** — looped installs run with `failed_when: false` plus per-failure reports; the enclosing `block/rescue` prints group-level failures (`block` accepts no loop member).
6. **Bounded escalation** — exactly three root DNF task sites plus one non-DNF root site (the firstboot include: system-path deploys + the marker write); everything else elevates only to `user.name`.
7. **Two-tier scoping** — Tier 2 defaults are `user_*`, registered facts are `_user_*`.
8. **set_fact producer-before-consumer split** — strategy facts and their consumers live in separate tasks, sequenced by placement only ([failure point 17](../../docs/failure-points.md); the inline comments in `go.yml` / `cargo.yml` are the whole enforcement).

## 🧩 Task Surface (`tasks/main.yml` dispatcher)

| Task file               | Gate (default)                                  | Purpose                                                                                     |
| ----------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `assert.yml`            | `user_assert_enabled` (`true`)                   | Fail-fast assertions: platform, package manager, identity, manifest shapes, firstboot manifest/conf contract, runs-as-expected-user            |
| `uv.yml`                | `user_install_uv` (`true`)                       | `uv python install {{ user_uv_python_version }}`; `uv` expected on PATH, installed elsewhere |
| `bun.yml`               | `user_install_bun` (`true`)                      | User-space Bun at `~/.bun/bin/bun`; skip-if-present guard                                   |
| `go.yml`                | `user_install_go` (`true`)                       | System-first Go tree, user-space `~/.local/go` fallback; go/gofmt symlinked into `~/.local/bin`; final min-version assert |
| `cargo.yml`             | `user_install_cargo` (`true`)                    | System-first cargo tree with rustup fallback; DNF-preferred crate installs; non-fatal per-crate failures (`--locked`) |
| `gnome-extensions.yml`  | `user_install_gnome_extensions` (`desktop_environment == 'gnome'`) | Installs the 4-UUID set from extensions.gnome.org; non-fatal per-UUID failures; skips headless hosts |
| `vscode-extensions.yml` | `user_install_vscode_extensions` (`false`)       | Opt-in management of the 68-entry list; CLI resolution: override → native `code` → `com.visualstudio.code` Flatpak → friendly skip |
| `firstboot.yml`         | `user_firstboot_enabled` (`true`) | Deploys the 7-file two-stage firstboot suite (root context) and is the single writer of the machine pull marker |

**Firstboot suite ownership.** `tasks/firstboot.yml` deploys the 7 files in
`files/firstboot/` — synced byte-identical from the osbuild SSOT
(`vendor/osbuild/roles/osbuild/files/firstboot/`) — to `/usr/local/bin` (×3),
`/etc/xdg/autostart` (×1) and `/etc/profile.d` (×3), and writes the machine
pull marker `~/.initial-firstboot` (the primary workstation user's home;
root:root 0644, ISO-8601 timestamp — phase-4 amendment: root's home is
unstat-able by the console user)
after a full-tag pull only (`ansible_run_tags` gate; see
`user_firstboot_marker_machine_tags`). The marker writer is stat-guarded
(byte-stable on re-runs); `user_firstboot_marker_write: false` leaves the
marker entirely alone, and `user_firstboot_marker_force: true` is its
skip-if-present override — partial-tag runs never write it regardless. The
include runs with `become: true, become_user: root` (ADR-6), unlike the rest
of the dispatcher. The suite is `user`-scoped: `--tags firstboot,user` selects
it (it no longer matches `common`). `assert.yml` extends the fail-fast gate to
the firstboot surface: each `user_firstboot_files` entry must reference an
existing source under `files/firstboot/` with an SSOT-shaped destination
(`/usr/local/bin` 0755 or `/etc/profile.d`/`/etc/xdg/autostart` 0644), the
marker path must be an absolute path ending in `.initial-firstboot` inside
the workstation home — the phase-4 home-location amendment: `user.home` (or
`/home/<user>`) is the one place the non-root console user can stat it, the
marker being `root:root 0644` and written by the pull (`/root` is unstat-able
by non-root users) — and, when present, `/etc/syncopated-user.conf` must parse
a `WORKSTATION_USER=<account>` line.

**Parity gate (`tests/check_firstboot_parity.yml`).** The suite must stay
byte-identical to the osbuild SSOT; editing one side without the other turns
this gate red with a named per-file diff:

```bash
ansible-playbook roles/user/tests/check_firstboot_parity.yml -i roles/user/tests/inventory
```

The playbook gates against the osbuild singleton working tree
(`../../osbuild/roles/osbuild/files/firstboot/`, resolved relative to the
playbook at runtime) and reports the pinned `vendor/osbuild` copy
informationally only — that comparison stays red until the final submodule
re-pin and is never a failure. The run is read-only (`--check` optional).

**The two decision trees share one shape.** Each probes the system binary at `/usr/bin/go` / `/usr/bin/cargo` — never via PATH, which can mask the system one with a user-space install — probes `dnf info`, escalates once for a root DNF install, rescues, re-probes, then resolves and consumes the strategy in separate `set_fact` tasks. Go falls back to the official tarball at `~/.local/go`; cargo falls back to rustup, with a TMPDIR noexec guard that redirects builds to `~/.cargo/tmp`.

**Dispatcher notes.**

- The dispatcher opens with a `Starting user tasks` debug (tagged `["user", "always"]`), then the gated assert include, then an ungated `include_vars "{{ ansible_distribution }}.yml"` tagged `["user", "distro"]`.
- The VS Code binary is not installed here — [`roles/tools`](../tools/README.md) owns it as a real opt-in; this role manages extensions only, against whatever CLI is resolvable.

## 🔧 Key Variables

All defaults live in `defaults/main.yml` with full parity with `meta/argument_specs.yml` (35 variables).

| Variable | Default | Description |
| --- | --- | --- |
| `user_assert_enabled` | `true` | Gate pre-flight assertions (`tasks/assert.yml`) |
| `user_uv_python_version` | `"3.12"` | Python version installed via uv (Tier 1 override: `"3.14"`) |
| `user_install_uv` | `true` | Gate `uv python install` |
| `user_install_bun` | `true` | Gate user-space Bun installation |
| `user_bun_dest` | `{{ user.home \| default('/home/' ~ user.name) }}/.bun/bin/bun` | Bun binary destination |
| `user_bun_url` | `https://github.com/oven-sh/bun/releases/latest/download/bun-linux-x64.zip` | Bun release archive URL |
| `user_bun_force_install` | `false` | Skip-if-present override for Bun |
| `user_install_go` | `true` | Gate the Go decision tree |
| `user_go_min_version` | `"1.22"` | Minimum acceptable effective Go version |
| `user_go_version` | `"1.27.1"` | User-space Go tarball version |
| `user_go_url` | `https://go.dev/dl/go{{ user_go_version }}.linux-{{ arm64/amd64 }}.tar.gz` | Go tarball URL (arch from `ansible_architecture`) |
| `user_go_dest_dir` | `{{ user.home \| default(...) }}/.local/go` | User-space Go tree (go/gofmt symlinked into `~/.local/bin`) |
| `user_go_force_install` | `false` | Force the user-space Go reinstall |
| `user_install_cargo` | `true` | Gate the cargo/Rust decision tree |
| `user_cargo_force_install` | `false` | Force the rustup toolchain install |
| `user_cargo_force_crates` | `[]` | Crates always re-attempted despite presence |
| `user_cargo_rustup_url` | `https://sh.rustup.rs` | rustup installer URL |
| `user_cargo_min_system_version` | `"1.99.1"` | Minimum acceptable system cargo version |
| `user_cargo_crates` | 10-entry list | bottom, choose, git-cliff, gping, ripgrep_all, sd, gitui, eza, weathr, dua-cli |
| `user_cargo_crate_bin_map` | `bottom: btm`, `ripgrep_all: rga`, `dua-cli: dua`, `du-dust: dust` | Crate → binary name for skip-if-present probes |
| `user_cargo_crate_dnf_map` | `dua-cli`, `gitui`, `eza` | Crate → DNF package (DNF-preferred install) |
| `user_install_gnome_extensions` | `{{ (desktop_environment \| default('none')) == 'gnome' }}` | Managed only when GNOME is the target DE |
| `user_gnome_extensions` | 4-UUID list | GNOME Shell extension manifest |
| `user_gnome_extensions_force_install` | `false` | Force extension re-installation |
| `user_gnome_extensions_base_url` | `https://extensions.gnome.org` | Metadata/bundle base URL |
| `user_install_vscode_extensions` | `false` | Gate VS Code extension management (opt-in) |
| `user_vscode_command` | `""` | Optional CLI override; empty = auto-detect |
| `user_vscode_force_install` | `false` | Force extension re-installation |
| `user_vscode_extensions` | 68-entry list | Marketplace extension manifest |
| `user_firstboot_enabled` | `true` | Gate the 7-file two-stage firstboot suite |
| `user_firstboot_files` | 7-entry list | The suite manifest (`{ src, dest, owner, group, mode }`); mirror of the osbuild SSOT injection table |
| `user_firstboot_marker_path` | `{{ user.home \| default('/home/' ~ user.name) }}/.initial-firstboot` | Machine pull-success marker (this role is its single writer; lives in the workstation home — `/root` is unstat-able by non-root users) |
| `user_firstboot_marker_write` | `true` | Escape hatch that leaves the marker untouched |
| `user_firstboot_marker_force` | `false` | Skip-if-present override for the marker writer (re-stamps the timestamp) |
| `user_firstboot_marker_machine_tags` | 14-tag list | Tag selection that counts a pull as full convergence for the marker gate |

### 🌐 Tier 1: Host & Domain Variables (`inventory/group_vars/all.yml`)

Supplied by inventory, never created or mutated by this role:

| Variable | Example | Description |
| --- | --- | --- |
| `user.name` | `b08x` | Primary workstation user account name |
| `user.home` | `/home/b08x` | Home directory path (absorbed lazily via `user.home \| default('/home/' ~ user.name)`) |
| `user.uid` | — | Optional; matched against the effective UID by `assert.yml` |
| `user.group`, `user.shell`, `user.secondary_groups` | — | Identity facts owned by the Tier 1 inventory; not consumed by this role |
| `desktop_environment` | `gnome` | Lazily consumed by `user_install_gnome_extensions` |
| `user_uv_python_version` | `"3.14"` | Tier 1 override of the role default `"3.12"` |
| `workstation_path_dirs` | 7-entry list | `~/.local/bin`, `~/.cargo/bin`, `~/go/bin`, `~/.bun/bin`, `/usr/local/bin`, `/usr/bin`, `/bin` — the PATH contract the role's destinations depend on |

### 🏷️ Registered Variables

On the dispatched surface, every register name uses the `_user_*` prefix (`_user_go_strategy`, the `_user_cargo_strategy` family, `_user_gnome_install_targets`, `_user_vscode_targets`). The claim is not total for the role directory: one orphan task file registers an unprefixed fact (see Known Limitations).

## 🏷️ Tags

| Tag | Purpose |
| --- | --- |
| `user` | All tasks in the role |
| `always` | Opening debugs and the assert include |
| `assert` | Pre-flight assertions |
| `distro` | Ungated distribution variable loading |
| `uv` | uv Python runtime |
| `bun` | User-space Bun runtime |
| `go` | Go decision tree |
| `cargo` | Rust/cargo decision tree and crate manifest |
| `gnome-extensions` | GNOME Shell extension management |
| `vscode-extensions` | VS Code extension management |
| `firstboot` | The two-stage firstboot suite (root-context include) |

## 🛡️ Layer Boundary & Escalation

Escalation is bounded, not accidental — three root DNF task sites inside the two decision trees, plus one non-DNF root-context include (firstboot), and nowhere else:

| Site                | Package(s)               | When                                                                |
| ------------------- | ------------------------ | -------------------------------------------------------------------- |
| `go.yml:81-82`      | `golang`                 | System Go absent; `golang` available via DNF                        |
| `cargo.yml:134-135` | `cargo`                  | System cargo absent; `cargo` available via DNF                      |
| `cargo.yml:389-390` | `dua-cli`, `gitui`, `eza` | DNF-preferred crate installs from `user_cargo_crate_dnf_map`         |
| `firstboot.yml` (dispatcher include, L83) | — (files, not packages) | Every firstboot-enabled run: the 7 system-path deploys and the `~/.initial-firstboot` marker write (`become: true, become_user: root` — the role's only non-DNF root escalation) |

Every `apply` block, the dispatcher, and the assert include elevate only to `user.name`. Beyond that boundary:

- No shell rc writes, no `~/.cargo/config.toml` — enforced by `rustup-init -y --no-modify-path` (`cargo.yml`), not convention.
- PATH comes from Tier 1 `workstation_path_dirs` plus Layer 2 rc files: go/gofmt symlinks land in `~/.local/bin`, Bun in `~/.bun/bin`.
- Force-override pairs gate every skip-if-present probe: `user_bun_force_install`, `user_go_force_install`, `user_cargo_force_install`, `user_cargo_force_crates`, `user_gnome_extensions_force_install`, `user_vscode_force_install`.
- The GNOME dconf enable step is a monotonic union: extensions are enabled, never disabled; a UUID removed from the manifest leaves the installed extension untouched — deliberate, not an oversight.

## 🚀 Playbook Integration & Usage

The role has two callers: `local.yml:447-450`, the repo-root playbook that `ansible-pull` runs as part of the firstboot bootstrap sequence (it invokes the role via `include_role` with `tags: ["user", "assert"]`), and `playbooks/workstation.yml:101-102`, typically run from the primary workstation (the controller host), passing `tags: ["user", "system"]`. The assert include's `always` tag covers both callers.

```yaml
- name: User Workstation Setup
  hosts: workstations
  become: true
  become_user: "{{ user.name }}"
  roles:
    - role: user
      tags: ["user", "system"]
```

Running a single feature (illustrative — the `bun` and `go` gates live in `tasks/main.yml`):

```bash
ansible-playbook playbooks/workstation.yml --tags "bun,go"
```

## ⚠️ Known Limitations

- **Orphan task files.** `tasks/pip.yml` (tags `pip/base`) and `tasks/ranger.yml` (tags `ranger/base`; sets `become: true` with no `become_user`, so its effective user depends on the invoking play; registers the unprefixed `user_ranger_check`) are never dispatched by `tasks/main.yml` — documented migration residue whose tag sets can never match a play reaching the role through the dispatcher. Dispatch or delete the two files.
- **RedHat/CentOS variance bound.** `assert.yml` admits `RedHat` and `CentOS`, but `vars/` ships only `Fedora.yml`, `AlmaLinux.yml`, `Rocky.yml`, and a near-empty `main.yml` — so the ungated `include_vars "{{ ansible_distribution }}.yml"` may fail on those distributions. A documented bound, not an observed failure.
- **Shell rc ownership.** The claims that `~/.zshenv` sources `~/.cargo/env` and `~/.zshrc` owns PATH additions come from code comments (`cargo.yml`) and are unverifiable from this repository; verify on a provisioned host.

## 📄 License

MIT (`meta/main.yml`)

## 👥 Author Information

b08x — Syncopated
