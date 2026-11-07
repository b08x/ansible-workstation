# Variable Precedence

This project adheres to the following variable precedence rules and naming conventions to prevent cross-role leakage and maintain clarity:

- **Tier 1 (Domain Scope)**: Unprefixed variables representing system-wide capabilities, user identity, or hardware intent.
  - Defined in `inventory/group_vars/all.yml` or specific `group_vars` / `host_vars`.
  - Examples: `user.*`, `intel_oneapi_install`, `nvidia_cuda_install`, `enable_third_party_repos`, `use_containers`, `use_kvm`, `has_cuda_device`, `has_vulkan_device`.

- **Tier 2 (Role Scope)**: Role-prefixed variables (`<role>_*`) that configure specific role behavior.
  - Defined in `roles/<role>/defaults/main.yml` and `roles/<role>/vars/main.yml`.
  - Examples: `tuning_cpupower_governor`, `common_auditd_max_log_file`, `user_bun_dest`.
  - Defaults are evaluated lazily: never reference, in `defaults/`, a variable that is set via `set_fact` later in the role ([`failure point 17`](failure-points.md#17-ansible-defaults-with-jinja2-expressions-evaluate-lazily)).

- **Task Registrations**: Variables created via `register:` within a task MUST use the `<role>_*` prefix.
  - Why: Registered variables have global host scope in Ansible and will collide across roles if left generic ([`failure point 12`](failure-points.md#12-role-scoped-variables-need-the-role-prefix)).
  - `set_fact` variables have global host scope but no visibility: if Role B depends on a variable set by Role A, declare the dependency — via `meta/main.yml`, a documented variable contract, or Tier 1 inventory ([`failure point 18`](failure-points.md#18-implicit-ordering-dependencies-between-roles-break-silently)).

## Precedence Chain

When multiple sources define the same variable, Ansible resolves it in the following order (from lowest to highest precedence):

1. **Role defaults** (`roles/*/defaults/main.yml`)
2. **Group variables** (`inventory/group_vars/*`)
3. **Host variables** (`inventory/host_vars/*`)
4. **Extra vars** (passed via CLI `-e` flag)

## A Worked Example, Traced Through the Tree

Every link in the chain below is verifiable in this repository:

- `tuning_cpupower_governor` defaults to `powersave` in
  `roles/tuning/defaults/main.yml` — step 1, the floor.
- `inventory/host_vars/ninjabot.yml` sets `tuning_cpupower_governor:
  performance` — host variables (step 3) outrank role defaults, so ninjabot
  runs `performance`.
- Extra vars outrank everything: `ansible-playbook playbooks/workstation.yml
  -e desktop_ui_environment=cosmic` overrides the `none` (headless) default in
  `roles/desktop_ui/defaults/main.yml` for exactly one run (step 4).

The tiers also meet on purpose: `inventory/host_vars/tinybot.yml` sets the
Tier 1 `intel_oneapi_install: true`, and `roles/gpu/defaults/main.yml`
consumes it as `gpu_install_intel_oneapi: "{{ intel_oneapi_install |
default(false) | bool }}"` — a Tier 2 default that defers to a Tier 1 fact
of the machine. The same pattern drives the NVIDIA stack: the Tier 1
`nvidia_cuda_install` flag (unset on every current host) is consumed as the
Tier 2 `gpu_install_nvidia` default of the `gpu` role.
