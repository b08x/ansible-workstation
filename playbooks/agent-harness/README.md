# Agent Harness Playbooks

Standalone playbooks that provision the coding agent CLIs (and the
Antigravity Hub + IDE GUI) on workstation hosts. These playbooks are opt-in:
nothing in `local.yml` or `playbooks/workstation.yml` imports them — run the
one you want, when you want it.

All four plays target the `workstations` group, run with `become: false` as
the unprivileged connection user, and gather facts explicitly in `pre_tasks`
(same shape as `playbooks/tts.yml`) so cached root-gathered facts never leak
in via the jsonfile fact cache.

## Claude Code

```bash
ansible-playbook playbooks/agent-harness/claude.yml
```

| Variable | Default | Description |
|---|---|---|
| `claude_user` | `{{ user.name \| default(ansible_user_id) }}` | Target user. Only effective when set to the connection user (see note below). |
| `claude_user_home` | `{{ user.home \| default(ansible_env.HOME) }}` | Home directory of the target user. |
| `claude_local_bin` | `{{ claude_user_home }}/.local/bin` | User binary directory for the `claude` binary. |
| `claude_npm_package` | `@anthropic-ai/claude-code` | npm package installed via the user prefix. |
| `claude_force_install` | `false` | Reinstall even if the `claude` binary already exists. |

- **Tags**: `claude`, `agents` (plus `assert` + `always` on the pre-flight checks, so
  `--tags assert` runs the pre-flight only).
- **Prerequisites**: npm — installed by the base role (`roles/common`
  runtimes). The play fails fast in `pre_tasks` with a clear message when
  npm is absent and the binary is not yet installed (or
  `claude_force_install: true`).

## OpenCode

```bash
ansible-playbook playbooks/agent-harness/opencode.yml
```

| Variable | Default | Description |
|---|---|---|
| `opencode_user` | `{{ user.name \| default(ansible_user_id) }}` | Target user. Only effective when set to the connection user (see note below). |
| `opencode_user_home` | `{{ user.home \| default(ansible_env.HOME) }}` | Home directory of the target user. |
| `opencode_local_bin` | `{{ opencode_user_home }}/.local/bin` | User binary directory for the `opencode` binary. |
| `opencode_npm_package` | `opencode-ai` | npm package installed via the user prefix. |
| `opencode_force_install` | `false` | Reinstall even if the `opencode` binary already exists. |

- **Tags**: `opencode`, `agents` (plus `assert` + `always` on the pre-flight checks, so
  `--tags assert` runs the pre-flight only).
- **Prerequisites**: npm — installed by the base role (`roles/common`
  runtimes). The play fails fast in `pre_tasks` with a clear message when
  npm is absent and the binary is not yet installed (or
  `opencode_force_install: true`).

## Crush

```bash
ansible-playbook playbooks/agent-harness/crush.yml
```

| Variable | Default | Description |
|---|---|---|
| `crush_user` | `{{ user.name \| default(ansible_user_id) }}` | Target user. Only effective when set to the connection user (see note below). |
| `crush_user_home` | `{{ user.home \| default(ansible_env.HOME) }}` | Home directory of the target user. |
| `crush_local_bin` | `{{ crush_user_home }}/.local/bin` | User binary directory for the `crush` symlink. |
| `crush_go_bin` | `{{ crush_user_home }}/go/bin` | Go binary directory holding the compiled `crush` binary. |
| `crush_go_package` | `github.com/charmbracelet/crush@latest` | Go module compiled via `go install`. |
| `crush_force_install` | `false` | Reinstall even if `crush` already exists in `~/.local/bin` or `~/go/bin`. |

- **Tags**: `crush`, `agents` (plus `assert` + `always` on the pre-flight checks, so
  `--tags assert` runs the pre-flight only).
- **Prerequisites**: Go — provisioned by the `tools` role
  (`ansible-playbook playbooks/workstation.yml --tags go`). The play fails
  fast in `pre_tasks` with a clear message when `go` is absent and `crush`
  is not yet installed (or `crush_force_install: true`).

## Antigravity (CLI `agy` + Hub & IDE)

```bash
ansible-playbook playbooks/agent-harness/antigravity.yml                  # CLI + GUI (present)
ansible-playbook playbooks/agent-harness/antigravity.yml -e antigravity_state=absent   # remove Hub & IDE
```

| Variable | Default | Description |
|---|---|---|
| `antigravity_user` | `{{ user.name \| default(ansible_user_id) }}` | Target user. Only effective when set to the connection user (see note below). |
| `antigravity_user_home` | `{{ user.home \| default(ansible_env.HOME) }}` | Home directory of the target user. |
| `antigravity_local_bin` | `{{ antigravity_user_home }}/.local/bin` | User binary directory for the `agy` CLI. |
| `antigravity_install_url` | `https://antigravity.google/cli/install.sh` | URL of the `agy` CLI install script. |
| `antigravity_force_install` | `false` | Re-run the CLI install script even if `agy` already exists. |
| `antigravity_install_gui` | `{{ auto_enable_desktop \| default(true) \| bool }}` | Gate for the Hub & IDE GUI blocks. |
| `antigravity_state` | `present` | Hub & IDE state: `present` installs, `absent` removes. |
| `antigravity_hub_url` | `https://storage.googleapis.com/.../Antigravity.tar.gz` | Tarball URL for the Antigravity Hub. |
| `antigravity_ide_url` | `https://edgedl.me.gvt1.com/.../Antigravity%20IDE.tar.gz` | Tarball URL for the Antigravity IDE. |

- **Tags**: `antigravity`, `agents` (plus `always` on the pre-flight fact
  gather); the GUI install block also carries `install` and the GUI remove
  block `uninstall`.
- **Prerequisites**: none beyond network access — the `agy` CLI install
  script is downloaded and executed as the connection user; the GUI tasks
  escalate with `become: true` only where they touch `/opt` and
  `/usr/share/applications` (passwordless sudo required).

## Notes

- **Opt-in**: running a playbook here is the opt-in; there is no
  `<agent>_install` flag. Opt out of a single agent's GUI part with
  `-e antigravity_install_gui=false` or select tasks with `--tags`.
- **Config stays in Yadm (Layer 2)**: these playbooks install binaries only.
  Agent config files (`~/.claude/settings.json`,
  `~/.config/crush/crushrc`, `~/.config/opencode/`, Antigravity settings,
  MCP definitions, and shared agent skills) remain managed by the Yadm
  dotfiles — Ansible never writes into paths Yadm owns.
- **`<agent>_user` caveat**: the plays run as the SSH connection user and
  drop the old `become_user` escalation. Setting `<agent>_user` (or
  `<agent>_user_home`) only takes effect when it matches the connection
  user — overriding it to a different user will not change where the
  binaries land.
