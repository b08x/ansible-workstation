# Memory Consolidation

## Strategies and Hard Rules

### Anti-patterns and Pitfalls

**Context**: When running Libvirt VMs (e.g., via Vagrant) on a host that also runs Docker.

**Pattern**: Prevent silent network failures caused by Docker's strict `FORWARD` DROP policy conflicting with Libvirt's `nftables` bridge routing.
```yaml
approach: |
  Explicitly allow Libvirt bridge interfaces (`virbr+`) to forward traffic in Docker's custom iptables chain (`DOCKER-USER`).
validation: VM should be able to ping an external IP (e.g., 8.8.8.8) or download packages without curl timeouts.
examples:
  - case: Vagrant/Libvirt VM silently hangs on network operations (e.g., dnf update)
    implementation: |
      sudo iptables -I DOCKER-USER -i virbr+ -j ACCEPT
      sudo iptables -I DOCKER-USER -o virbr+ -j ACCEPT
```

**Avoid**: Assuming Libvirt's native `nftables` rules are sufficient when Docker is installed. Docker manages `iptables` and its default `FORWARD DROP` policy supersedes `nftables` accepts.

- **Docker iptables hijack**: Causes silent drops of `virbr+` outbound NAT traffic.
- **Vagrant provisioning hangs**: Network timeouts lead to infinite hangs during inline shell scripts without clear error messages.

**Confidence**: High

**Source**: 2026-09-02 Root Cause Trace
### Homebrew on Linux: prefix is derived from the invocation path

**Context**: Installing, relocating, or repairing Homebrew on a Linux workstation.

**Pattern**: Never expose `brew` through a symlink placed outside its own prefix. `bin/brew` computes `HOMEBREW_PREFIX` from the path it was *invoked through* (grandparent of the invoked file), while `HOMEBREW_REPOSITORY` comes from the realpath. A symlink in a shared `bin/` silently splits the two and Homebrew links every keg into the wrong tree.
```yaml
approach: |
  Install at the official prefix and expose it only via shellenv:
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"
  Never: ln -s <repo>/bin/brew ~/.local/bin/brew
validation: |
  brew --prefix, brew --repo and brew --cellar must agree on one tree:
    prefix=/home/linuxbrew/.linuxbrew  repo=<prefix>/Homebrew  cellar=<prefix>/Cellar
  A prefix that is the parent of a shared bin/ (e.g. ~/.local) means it is misconfigured.
examples:
  - case: brew --prefix reports ~/.local while the repo lives in ~/.local/apps/homebrew
    implementation: |
      # ~29k keg symlinks scatter through ~/.local/{bin,lib,share,include,etc,opt,sbin,var}.
      # They are identifiable by link TARGET, so cleanup is precise:
      find ~/.local -lname '*apps/homebrew*' -not -path "$HOME/.local/apps/homebrew/*" -delete
      # Verify non-brew entries survive by counting ~/.local/bin before and after.
  - case: choosing a prefix on Linux
    implementation: |
      # /home/linuxbrew/.linuxbrew is the ONLY prefix that receives prebuilt bottles.
      # Any other prefix (~/homebrew, ~/.local) builds every formula from source.
```

**Avoid**: Hand-written `export PATH="<prefix>/bin:$PATH"` in place of `brew shellenv`.

- **Bare PATH export**: leaves `HOMEBREW_PREFIX`/`CELLAR`/`REPOSITORY`/`MANPATH`/`INFOPATH` unset, which is exactly what lets brew infer a prefix from its invocation path.
- **Non-standard prefix**: disables bottles; a 29-formula restore becomes hours of compiling instead of minutes.
- **Blanket empty-dir pruning after cleanup**: `~/.local` empty dirs include non-brew ones (`gnome-software`, `ibus-table`); removing brew symlinks does not make every resulting empty dir brew's.

**Confidence**: High

**Source**: 2026-09-05 Homebrew relocation (~/.local → /home/linuxbrew/.linuxbrew)

### Shell: commands that read stdin drain `while read` loops

**Context**: Any `while read` loop over a list where the body runs an external command (`brew install`, `ssh`, `ansible-playbook`, `apt`, `docker`).

**Pattern**: Redirect the body's stdin, or iterate on a non-zero file descriptor. A command that reads stdin consumes the *same* descriptor the loop iterates, so the loop exits early — silently, with status 0.
```yaml
approach: |
  Prefer mapfile + for, and pin stdin per invocation:
    mapfile -t ITEMS < <(producer)
    for i in "${ITEMS[@]}"; do cmd "$i" </dev/null || echo "!! FAILED: $i"; done
  Or iterate on fd 9:  while read -u 9 i; do cmd "$i"; done 9< list
validation: Count iterations actually attempted and compare against the input list length.
examples:
  - case: producer | while read f; do brew install "$f"; done
    implementation: |
      # Ran 2 of 29 formulae, exited 0, emitted no error.
      # brew install consumed the remaining 27 lines from the pipe.
      brew install "$f" </dev/null   # fix
```

**Avoid**: Treating a zero exit status from such a loop as proof the loop completed.

- **Silent early exit**: no error is printed and `$?` is 0; the failure is invisible in logs.
- **`ssh` in a loop**: the classic instance — always `ssh -n` or `ssh ... </dev/null`.

**Confidence**: High

**Source**: 2026-09-05 Homebrew formula restore

### Verification Checklist

**Context**: Reporting completion of any batch/idempotent operation (package restores, playbook runs, bulk file ops).

**Pattern**: Verify against declared desired state, not against the operation's own log.
```yaml
approach: |
  Capture a manifest BEFORE a destructive change, then diff observed state against it AFTER.
validation: The diff must be empty; an empty failure-grep is not equivalent evidence.
examples:
  - case: confirming a package restore
    implementation: |
      # Weak: grep '^!!' restore.log            -> clean even when the loop never ran
      # Strong: comm -23 <(sort manifest) <(brew list --formula | sort)
  - case: before any destructive host change
    implementation: |
      brew tap > manifest; brew leaves >> manifest   # capture desired state first
```

**Avoid**: Declaring success from log absence-of-errors, or from a command's exit status alone.

- **Absence-of-error grep**: proves nothing about steps that were never attempted.
- **No pre-change manifest**: leaves no ground truth to verify or roll back against.

**Confidence**: High

**Source**: 2026-09-05 Homebrew restore (mis-reported as complete on a clean failure-grep)

# Documentation Lookup

## Use Context7 MCP for Loading Documentation

Context7 MCP is available to fetch up-to-date documentation with code examples.
Prefer it over training-data recall for module arguments, plugin behavior, and
collection/rulebook schemas — Ansible's module surface changes across releases.

**Recommended library IDs**:

- `/ansible/ansible-documentation` - Ansible package + ansible-core user docs (playbooks, roles, inventory, vars precedence, collection structure). Primary reference. Versioned: `v2.16.14`, `v2_17_13`, `v2_15_10` — append a version when pinning to a specific core release.
- `/ansible/ansible` - The ansible-core source repository. Use for module/plugin implementation detail and changelog behavior not covered by the prose docs.
- `/ansible/ansible-rulebook` - Event-Driven Ansible: rulebook syntax, event sources, conditions, throttling, and actions.
- `/ansible/molecule` - Molecule testing framework: scenario layout, drivers, verifiers, and converge/idempotence gates. Relevant to `roles/*/molecule/`.
- `/websites/dspy_ai` - DSPy: signatures, modules/predictors, optimizers (MIPROv2, GEPA), evaluation. Relevant to the `llm_analyzer` callback and `scripts/llm_trainset.py` — see `plugins/callback/README.md`.
- `/stanfordnlp/dspy` - DSPy source repository. Use for implementation detail and version-specific behavior the docs site omits.

**Usage**: pass the ID directly to `query-docs` — no `resolve-library-id` call needed
when the ID is already in `/org/project` form.
