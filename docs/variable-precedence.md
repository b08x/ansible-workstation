# Variable Precedence

This project adheres to the following variable precedence rules and naming conventions to prevent cross-role leakage and maintain clarity:

- **Tier 1 (Domain Scope)**: Unprefixed variables representing system-wide capabilities, user identity, or hardware intent.
  - Defined in `inventory/group_vars/all.yml` or specific `group_vars` / `host_vars`.
  - Examples: `user.*`, `intel_oneapi_install`, `enable_third_party_repos`, `use_containers`, `use_kvm`.

- **Tier 2 (Role Scope)**: Role-prefixed variables (`<role>_*`) that configure specific role behavior.
  - Defined in `roles/<role>/defaults/main.yml` and `roles/<role>/vars/main.yml`.
  - Examples: `osbuild_blueprint_name`, `base_package_list`.

- **Task Registrations**: Variables created via `register:` within a task MUST use the `<role>_*` prefix.
  - Why: Registered variables have global host scope in Ansible and will collide across roles if left generic.

## Precedence Chain

When multiple sources define the same variable, Ansible resolves it in the following order (from lowest to highest precedence):

1. **Role defaults** (`roles/*/defaults/main.yml`)
2. **Group variables** (`inventory/group_vars/*`)
3. **Host variables** (`inventory/host_vars/*`)
4. **Extra vars** (passed via CLI `-e` flag)
