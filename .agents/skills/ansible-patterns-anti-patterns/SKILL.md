---
name: ansible-patterns-anti-patterns
description: "Use when auditing, designing, or refactoring Ansible roles and playbooks. Catalogues 15 design patterns and anti-patterns observed in real-world Ansible projects with per-role violation matrices."
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Ansible Design Patterns & Anti-Patterns

## Overview

A field guide to 15 design patterns observed in real Ansible projects, extracted from tracing a multi-role, multi-distro workstation provisioning codebase. Each pattern includes the canonical form, where it appears, and the anti-pattern violations that break it. Use this to audit existing roles or prevent common mistakes when authoring new ones.

Companion to `ansible-best-practices-roles-modules` (Tim Appnel) which provides the theoretical framework. This skill provides the **concrete recognition patterns** — what it looks like in the wild when it's right, and what it looks like when it's wrong.

## When to Use

- Auditing a role for structural quality
- Refactoring a monolithic role into focused roles
- Onboarding to an existing Ansible codebase
- Designing a new role and want to avoid common traps
- Reviewing PRs that add or modify roles

**Don't use for:** Module implementation details (use `ansible-best-practices-roles-modules` ch03), syntax questions (use `ansible` by Geerling), or idempotency theory (use ch03 of either).

---

## The 15 Patterns

### 1. Task Dispatcher Pattern
**Purpose:** Decompose a role into composable subtask files.

```yaml
# GOOD: main.yml as dispatcher
- import_tasks:
    file: subtask.yml
  when: feature_flag|default(false)|bool == True
  tags: ['feature']
```

**Variants:**
| Variant | Guard | Example |
|---|---|---|
| Explicit bool | `var\|default(false)\|bool == True` | llmops |
| Bare boolean | `var\|bool` | nas |
| Defined check | `var is defined` | common |

**Anti-pattern:** Using three different dialects in the same codebase. Pick one.

---

### 2. Data-Driven Directory Creation
**Purpose:** Create directories from a definitions list with overridable defaults.

```yaml
# GOOD: identical filter chain everywhere
- file:
    dest: "{{ item.dest }}"
    state: directory
    owner: "{{ item.owner | default(some_default_owner) }}"
    group: "{{ item.group | default(some_default_group) }}"
    mode: "{{ item.mode | default(some_default_mode) }}"
    recurse: "{{ item.recurse | default(some_default_recurse) }}"
  with_items: "{{ definitions_list }}"
```

**Used by:** `common` (root dirs), `user` (home dirs), `llmops.yml` (data dirs), `theme` (root dirs).

**Anti-pattern:** Copying the filter chain but changing the variable prefix (e.g., `root_directory_default_*` vs `home_directory_default_*` vs `data_directory_default_*`). Consider extracting a reusable variable namespace.

---

### 3. Distro-Switching Pattern
**Purpose:** Handle multiple Linux distributions in one role.

| Dialect | Mechanism | When to Use |
|---|---|---|
| A: `include_vars` | `include_vars: file: vars/{{ ansible_distribution }}.yml` | Different variable sets per distro |
| B: `when` guards | `when: ansible_distribution == 'X'` | Different tasks per distro |
| C: Combined | Both A and B | Variables differ AND tasks differ |

**Anti-pattern:** Using dialect B with hardcoded package lists in `main.yml` instead of `include_vars` (docker, libvirt, python). The package lists should live in `vars/Archlinux.yml` and `vars/AlmaLinux.yml`.

**Rule:** If you have more than 2 `when: ansible_distribution ==` blocks in one file, switch to `include_vars`.

---

### 4. Git Clone + Template + Docker Compose Pattern
**Purpose:** Deploy a containerized service from source.

```yaml
# GOOD: full lifecycle
- block:
    - git: (clone repo)
    - template: (Dockerfile, docker-compose.yml, .env)
    - docker_compose: (stop → absent → create)
  become: False
```

**Deployment completeness tiers:**
| Tier | Actions | Services |
|---|---|---|
| Full lifecycle | clone → template → stop → teardown → create | flowise, chromadb |
| Clone + template | clone → template (no lifecycle) | agenta, wavjourney, deepafx, label-studio |
| Clone only | clone (no template, no start) | agnai, llmstack, anythingllm |

**Anti-pattern:** Tier 3 (clone-only) — the service is never started. These are incomplete deployments.

---

### 5. Pre-flight Check Block
**Purpose:** Detect hardware or environment capabilities before roles execute.

```yaml
# GOOD: runs before any roles
- block:
    - shell: (detect capability)
      register: result
    - set_fact: (set variable based on result)
  check_mode: False
  tags: always
```

**Anti-pattern:** Only using this in `full.yml` but not in `base.yml` or `workstation.yml`. If the architecture variable is needed by roles, all playbooks that use those roles should detect it.

---

### 6. Role Composition (Playbook Stacking)
**Purpose:** Layer playbooks to build up system capability.

```
base.yml:        OS layer (user → distro → common → network → audio → docker → libvirt → python → ruby)
workstation.yml: Desktop layer (desktop → theme → applications)
full.yml:        Union of all layers
llmops.yml:      Application layer (pre_tasks → llmops)
```

**Anti-pattern:** Duplicating role lists across playbooks instead of composing them. `full.yml` should be `include_playbook: base.yml` + `include_playbook: workstation.yml` if Ansible supported it. Since it doesn't, keep the lists in sync manually.

---

### 7. Tag-as-Select Pattern
**Purpose:** Enable selective execution of tasks and subtask groups.

```yaml
# Convention: role name = primary tag
- import_tasks: file: firewall.yml
  tags: ['firewall']

# Secondary tags for sub-features
- import_tasks: file: groups.yml
  tags: ['profile', 'shell']
```

**Anti-pattern:** Missing tags on any task. Every `import_tasks`, `template`, `copy`, and `file` task should have at least one tag.

---

### 8. Backup-on-Write Pattern
**Purpose:** Preserve previous file state before overwriting.

```yaml
template:
  src: ...
  dest: ...
  backup: True
```

**Rule:** Every `template` and `copy` task that writes to a config file should have `backup: True` or `backup: yes`.

**Anti-pattern:** Inconsistent use — some tasks have `backup: True`, others have `backup: yes`, some have neither.

---

### 9. Block-as-Unit Pattern
**Purpose:** Group related tasks with shared error handling or conditions.

```yaml
- block:
    - name: task 1
    - name: task 2
  become: False          # or
  ignore_errors: "{{ ansible_check_mode }}"  # or
  when: ansible_distribution == 'X'
```

**Common block guards:**
| Guard | Purpose | Example |
|---|---|---|
| `become: False` | Non-root deployment | llmops, docker, desktop, audio |
| `ignore_errors` | Check mode safety | user |
| `check_mode: False` | Always run, even in check | full.yml pre-flight |
| `when: distro` | Distro-specific packages | docker, libvirt, python |

---

### 10. Environment Injection Pattern
**Purpose:** Set environment variables for all tasks in a playbook.

```yaml
environment:
  PATH: "{{ ansible_env.PATH }}:/sbin:/bin:{{ path|join(':') }}"
  PKG_CONFIG_PATH: "/usr/share/pkgconfig:/usr/lib/pkgconfig:/usr/local/lib/pkgconfig"
  ZSH: "/usr/local/share/oh-my-zsh"
  DISPLAY: ":0"
```

**Anti-pattern:** Copy-pasting the same `environment:` block across playbooks. Extract to a shared vars file or `group_vars/all.yml`.

---

### 11. Conditional Feature Flags Pattern
**Purpose:** Gate optional features behind variables.

| Pattern | Syntax | Example |
|---|---|---|
| Explicit bool | `var\|default(false)\|bool == True` | llmops, libvirt |
| Bare boolean | `var\|bool` | applications, nas |
| Defined check | `var is defined` | common, desktop |
| Boolean variable | `var\|bool` in group_vars | workstation |

**Anti-pattern:** Mixing dialects in the same role. Pick one per role, ideally explicit bool with `default(false)`.

---

### 12. Post-task Lifecycle Pattern
**Purpose:** Run cleanup, reboot, or firewall rules after all roles complete.

```yaml
post_tasks:
  - name: Cleanup
    script: "/usr/local/bin/cleanup.sh"
    when: cleanup is defined

  - name: Reboot host
    reboot:
    async: 1
    poll: 0
    ignore_errors: True
    when: reboot is defined
```

**Anti-pattern:** Using `post_tasks` for firewall rules (llmops.yml) instead of putting them in the role. Firewall configuration belongs in a role, not a playbook post-task.

---

### 13. Debug-as-Progress-Indicator Pattern
**Purpose:** Print a message at role entry for log readability.

```yaml
- name: Starting docker tasks
  debug:
    msg: "Starting docker tasks"
```

**Anti-pattern:** Inconsistent adoption — some roles have it (docker, audio, network, libvirt), others don't (user, distro, common, python, shell, desktop, theme). Standardize: every role should either have it or not.

---

### 14. Handler Notification Pattern
**Purpose:** Trigger service restarts on config changes.

```yaml
# In task:
template:
  src: sshd_config.j2
  dest: /etc/ssh/sshd_config
  backup: True
  notify: restart sshd

# In handlers/main.yml:
- name: restart sshd
  systemd:
    name: sshd
    state: restarted
```

**Anti-pattern:** Dead handlers — handlers defined but never notified. Example: `reload firewalld` in llmops has no task that notifies it.

---

### 15. Data-Driven Firewall Pattern
**Purpose:** Manage firewall ports from a variable list.

```yaml
# GOOD: variable-driven
firewalld:
  port: "{{ item }}"
  state: enabled
  permanent: yes
with_items: "{{ allowed_ports }}"
```

**Anti-pattern:** Hardcoding port lists in the playbook instead of `group_vars` or role defaults. Example: llmops.yml has 12 hardcoded port entries.

---

## Per-Role Violation Matrix

Use this to audit which patterns each role follows or violates.

| Role | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | defs/vars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| user | ✅ | ✅ | — | — | — | ✅ | ✅ | ⚠️ | ✅ | — | ✅ | — | ❌ | ❌ | — | ❌ |
| distro | ✅ | — | ✅ | — | — | ✅ | ✅ | — | — | — | — | — | ❌ | ❌ | — | ⚠️ |
| common | ✅ | ✅ | — | — | — | ✅ | ✅ | ✅ | — | — | ✅ | — | ❌ | ✅ | — | ✅ |
| network | ✅ | — | — | — | — | ✅ | ✅ | — | — | — | — | — | ✅ | ✅ | — | ⚠️ |
| audio | ✅ | — | ⚠️ | — | — | ✅ | ✅ | — | ✅ | — | — | — | ✅ | ✅ | — | ✅ |
| docker | ✅ | — | ⚠️ | — | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | ✅ | — | ✅ |
| libvirt | ✅ | — | ⚠️ | — | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | ❌ | — | ⚠️ |
| python | — | — | ⚠️ | — | — | ✅ | ✅ | — | ✅ | — | — | — | ❌ | ❌ | — | — |
| shell | ✅ | — | — | — | — | ✅ | ✅ | — | — | — | — | — | ❌ | ❌ | — | — |
| desktop | ✅ | — | ✅ | — | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ❌ | ✅ | — | ✅ |
| theme | ✅ | ✅ | ✅ | — | — | ✅ | ✅ | ✅ | ✅ | — | — | — | ❌ | ❌ | — | ✅ |
| applications | ✅ | — | ✅ | — | — | ✅ | ✅ | — | ✅ | — | ✅ | — | ✅ | ❌ | — | ✅ |
| nas | ✅ | — | — | — | — | — | ✅ | — | — | — | ⚠️ | — | ❌ | ❌ | — | ⚠️ |
| llmops | ✅ | — | ⚠️ | ⚠️ | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ❌ | ❌ | ⚠️ | ❌ |

**Column key:** 1=Dispatcher, 2=DataDirs, 3=DistroSwitch, 4=Git+Tmpl, 5=PreFlight, 6=Composition, 7=Tags, 8=Backup, 9=Block, 10=EnvInj, 11=Flags, 12=PostTask, 13=Debug, 14=Handler, 15=Firewall

---

## Most Common Violations (ranked by frequency)

| # | Violation | Roles | Fix |
|---|---|---|---|
| 1 | No debug entry message | 10/15 | Add `debug: msg: "Starting X tasks"` to every role or remove from all |
| 2 | No handlers file | 8/15 | Create handlers or remove unused handler definitions |
| 3 | defaults/vars inversion | user, llmops | Move overridable config to `defaults/main.yml` |
| 4 | Distro-switching with hardcoded lists | docker, libvirt, python | Move package lists to `vars/{{ distro }}.yml` |
| 5 | Feature flag dialect mixing | nas, llmops | Standardize on `var\|default(false)\|bool == True` |
| 6 | Dead handler | llmops | Remove `reload firewalld` or add `notify` to firewall tasks |
| 7 | Incomplete deployment | llmops | Add template + docker_compose lifecycle to agnai, llmstack, anythingllm |
| 8 | Hardcoded firewall ports | llmops | Move to `group_vars` or role defaults |

---

## Verification Checklist

When auditing a role, check:

- [ ] Every `import_tasks` has a `tags` list
- [ ] Every `template`/`copy` has `backup: True`
- [ ] `defaults/main.yml` contains overridable config; `vars/main.yml` contains internal-only data
- [ ] Distro-switching uses consistent dialect across all tasks in the role
- [ ] Feature flags use consistent syntax (`default(false)|bool == True` or `is defined`, not both)
- [ ] No handlers are defined without a corresponding `notify`
- [ ] No `post_tasks` in playbooks do work that belongs in a role
- [ ] Container deployments include a full lifecycle (clone → template → start)
- [ ] Debug entry message exists (or is consistently absent across all roles)
- [ ] Firewall ports are variable-driven, not hardcoded
- [ ] `environment:` blocks are shared, not copy-pasted
- [ ] `group: devops` or other group references are declared in `defaults/` or validated

## Common Pitfalls

1. **Empty `defaults/main.yml`.** If all config is in `vars/`, users cannot override anything without forking the role. Move user-facing config to `defaults/`.

2. **Three dialects of feature flags.** Pick one project-wide: `var|default(false)|bool == True` is the most explicit.

3. **Incomplete LLMOps deployments.** Cloning a repo without templating docker-compose or starting containers leaves the service non-functional.

4. **Dead handlers.** A handler defined in `handlers/main.yml` that no task notifies is dead code. Remove it.

5. **Hardcoded values in playbooks.** Port lists, paths, and group names in playbook `post_tasks` or `pre_tasks` should be in `group_vars/` or role defaults.

6. **Copy-pasted environment blocks.** The same `environment:` block in `base.yml`, `workstation.yml`, and `full.yml` should be extracted to a shared vars file.

7. **Inconsistent backup syntax.** `backup: True` and `backup: yes` both work, but mixing them makes the codebase look sloppy. Pick one.

8. **Missing progress indicators.** Some roles print "Starting X tasks", others don't. Pick one convention and apply it everywhere.
