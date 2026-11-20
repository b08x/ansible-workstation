# Variable Precedence

This project adheres to the following variable precedence rules and naming conventions to prevent cross-role leakage and maintain clarity:

- **Tier 1 (Domain Scope)**: Unprefixed variables representing system-wide capabilities, user identity, or hardware intent.
  - Defined in `inventory/group_vars/all.yml` or specific `group_vars` / `host_vars`.
  - Examples: `user.*`, `desktop_environment`, `enable_third_party_repos`, `workstation_prompt_reboot`, `has_cuda_device`, `has_vulkan_device`.

- **Tier 2 (Role Scope)**: Role-prefixed variables (`<role>_*`) that configure specific role behavior.
  - Defined in `roles/<role>/defaults/main.yml` and `roles/<role>/vars/main.yml`.
  - Examples: `tuning_cpupower_governor`, `common_auditd_max_log_file`, `gpu_install_nvidia`, `gpu_install_intel_oneapi`, `user_bun_dest`.
  - Defaults are evaluated lazily: never reference, in `defaults/`, a variable that is set via `set_fact` later in the role ([`failure point 17`](failure-points.md#17-ansible-defaults-with-jinja2-expressions-evaluate-lazily)).

- **Task Registrations & Internal State**: Variables created via `register:` within a task or private facts via `set_fact` MUST use the `_<role>_*` prefix (leading underscore) per refactoring rule R3.
  - Why: Registered variables have global host scope in Ansible and will collide across roles if left generic ([`failure point 12`](failure-points.md#12-role-scoped-variables-need-the-role-prefix)).
  - `set_fact` variables also possess global host scope: private role facts must use `_<role>_*`, and if Role B depends on a variable set by Role A, declare the dependency explicitly — via `meta/main.yml`, a documented variable contract, or Tier 1 inventory ([`failure point 18`](failure-points.md#18-implicit-ordering-dependencies-between-roles-break-silently)).

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
  -e desktop_environment=cosmic` overrides the `none` (headless) default defined in
  `inventory/group_vars/all.yml` for exactly one run (step 4), selecting COSMIC
  desktop convergence.

Tier 2 role flags (`gpu_install_intel_oneapi`, `gpu_install_nvidia`) default to `false` in
`roles/gpu/defaults/main.yml`. Individual hosts enable vendor hardware stacks in
`inventory/host_vars/<host>.yml` or via extra vars (`-e gpu_install_nvidia=true`), ensuring
role-scoped variables remain cleanly namespaced without ambiguous global alias shims.
