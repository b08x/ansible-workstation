# b08x.llmops whisper Role

A brief description of the role goes here.

## Requirements

Any pre-requisites that may not be covered by Ansible itself or the role should be mentioned here. For instance, if the role uses the EC2 module, it may be a good idea to mention in this section that the boto package is required.

## Role Variables

| Variable | Default | Description |
|---|---|---|
| `tts_assert_enabled` | `true` | Gate pre-flight assertion tasks (`tasks/assert.yml`) to fail fast on invalid environments. |
| `whisper_my_variable` | `"default_value"` | Demonstration string variable. |

## Tags

| Tag | Scope | Description |
|---|---|---|
| `tts` | Role | Applies to all tasks within the `tts` role. |
| `assert` | Validation | Executes pre-flight assertion tasks to validate system requirements. |
| `always` | System | Preamble debug logging. |


## Dependencies

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

## Example Playbook

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

```yaml
- name: Execute tasks on servers
  hosts: servers
  roles:
    - role: b08x.llmops.run
      run_x: 42
```

Another way to consume this role would be:

```yaml
- name: Initialize the run role from b08x.llmops
  hosts: servers
  gather_facts: false
  tasks:
    - name: Trigger invocation of run role
      ansible.builtin.include_role:
        name: b08x.llmops.run
      vars:
        run_x: 42
```

## Role Idempotency

Designation of the role as idempotent (True/False)

## Role Atomicity

Designation of the role as atomic if applicable (True/False)

## Roll-back capabilities

Define the roll-back capabilities of the role

## Argument Specification

Including an example of how to add an argument Specification file that validates the arguments provided to the role.

```yaml
argument_specs:
  main:
    short_description: Role description.
    options:
      string_arg1:
        description: string argument description.
        type: "str"
        default: "x"
        choices: ["x", "y"]
```

## License

<!-- TO-DO: Update the license to the one you want to use (delete this line after setting the license) -->
BSD

## Author Information

An optional section for the role authors to include contact information, or a website (HTML is not allowed).
