# action

Repo-local action plugins, loaded via `action_plugins = ./plugins/action` in
`ansible.cfg`. The three plugins here, one module, and a set of support files
form a diagnose-and-remediate pipeline for rootless Podman hosts. The
playbook `playbooks/remediate.yml` drives it.

The pipeline does one job. It reads the state of a failing host, asks a
language model what is wrong and how to fix it, checks the proposed fix
mechanically, shows it to you, and runs it only if you type `yes`. After the
run it checks the host again and asks you whether the fix worked. Fixes you
confirm are kept and offered as reference the next time a similar failure
appears on any host.

What the pipeline will not do:

- **The model never executes anything.** It returns text: a summary and a
  playbook. Ansible runs that playbook, after a human approves it.
- **Nothing runs without approval.** Without a terminal and without an
  explicit `-e remediation_approve=yes`, the run stops before execution.
- **The gather never changes the host.** It reports `changed: false` and runs
  the same read-only commands in `--check` mode.
- **A healthy host costs nothing.** If every container and pod is running, the
  run ends before any model call and records nothing.
- **Some drafts never reach you.** A draft that removes a Podman volume, or
  removes a working container before proving its replacement starts, is
  rejected automatically.

| File | Runs on | Role |
| :--- | :--- | :--- |
| `plugins/modules/remediation_gather.py` | target host | Read-only collector. Returns one JSON document. |
| `plugins/action/remediation_diagnose.py` | controller | Gather, health gate, then diagnosis and draft through the CLI. |
| `plugins/action/remediation_verify.py` | controller | Re-diagnoses fresh diagnostics after a remediation. |
| `plugins/action/remediation_record.py` | controller | Records an outcome; indexes the playbook on `success`. |
| `plugins/callback_utils/remediation_*.py` | controller | Support code; see [Process boundaries](#process-boundaries). |

Support code lives in [`../callback_utils/`](../callback_utils/README.md), not
here: Ansible imports every `*.py` in this directory as an action plugin.

## Quick start

Three things must exist on the controller:

1. The repo venv, created by `bin/setup`. The pipeline's model and database
   work runs in `.venv/bin/python`.
2. An LLM provider key. The pipeline reads the `[callback_llm_analyzer]`
   section of `ansible.cfg`, the same one the `llm_analyzer` callback uses, and
   the matching `<PROVIDER>_API_KEY` variable, such as `OPENROUTER_API_KEY`.
3. A local Ollama with the embedding model: `ollama pull embeddinggemma:latest`.

Run it from the repo root against one host:

```bash
ansible-playbook playbooks/remediate.yml -e target=tinybot
```

`target` is required. On a healthy host the run ends within seconds of the
gather. On a failing host the first task takes one to three minutes: two model
calls and an `ansible-lint` run.

## How a run works

A run has eleven stages. Stages 1 and 2 decide whether the rest happens at all.

**1. Gather** (target host, `remediation_gather`). Runs read-only commands and
returns one JSON document. Each section is an envelope `{ok, data, error}`, so
one failing command degrades one section instead of failing the task. Secret
values are redacted before the document leaves the host; see
[What the gather collects](#what-the-gather-collects).

**2. Health gate** (controller, no model). `remediation_health.assess` reads
container and pod state from the gather output. The host is *healthy* when
every container is `running`, no container reports `(unhealthy)`, and every
pod is `Running`. A healthy host ends the run here. A host with no containers
at all is **not** healthy: a service that has disappeared must not read as
"nothing to do". `-e remediation_force=true` skips the gate.

The gate also emits warnings for host faults that break containers later. The
one implemented today detects SELinux turned off by a `selinux=0` boot
argument, or turned off while `/etc/selinux/config` says otherwise.

**3. Diagnose** (controller, model call 1). The diagnostics are split and
trimmed first. Journal entries older than the most recent container start move
to `*_history` keys, so a failure that was already fixed is not presented as
live. The document is then cut to `REMEDIATION_CONTEXT_BUDGET` characters,
whole sections at a time, in this priority order: host, host security, SELinux
denials, mounts, pods (failing first), containers (failing first), error lines
from container logs, error-level journal entries. The model returns a summary,
a normalized host-independent error signature (for example
`podman:container_state_improper+shm_mount_einval`), the affected service, the
role in `roles/` that manages it, and a severity.

**4. Record and search** (controller, Ollama and DuckDB). The summary is
embedded with `embeddinggemma:latest` and the incident is appended to
`incidents.jsonl`. The embedding is computed before anything is written, so an
unreachable Ollama leaves no partial record. The store then rebuilds an
in-memory DuckDB `vss` HNSW index from the JSONL and returns the five nearest
incidents by cosine similarity. The new incident is always among them and is
dropped, which leaves up to four past incidents.

**5. Draft** (controller, template or model call 2). If a hand-written template
matches the signature, service and role, its playbook is used and no model is
called (`tier: template`). Otherwise the model drafts a playbook from the
diagnostics (`tier: llm`). Past incidents that score at or above
`REMEDIATION_SIMILARITY_THRESHOLD` *and* have a confirmed, indexed remediation
are passed to it as reference, with their playbook text. The model also
returns a rationale and one health check: an HTTP URL that must return 200, or
a container name for `podman healthcheck run`.

**6. Guards** (controller). The draft must pass five checks, in order. The
first failure rejects it; see [Guards](#guards).

**7. Approval** (controller, `ansible.builtin.pause`). The play prints the
incident, the tier, the signature, the summary, each similar past incident
with its score, and the **full** playbook. Type `yes` to continue. Anything
else, or no terminal, stops the run with *nothing was executed on the host*.

**8. Execute** (controller, `delegate_to: localhost`). The play runs
`ansible-playbook --inventory <remediation_inventory> --limit <host> <draft>`
as a child process, with `ANSIBLE_ROLES_PATH` pointing at the repo's `roles/`.

**9. Verify** (target host, then controller). The gather runs again.
`remediation_verify` re-diagnoses the fresh diagnostics with the same prompt
and reports `resolved: true` when the new signature is non-empty and differs
from the original. If resolved, the drafted health check runs.

**10. Confirmation** (controller, `ansible.builtin.pause`). The play prints the
new signature and the health check result and asks whether the service is
healthy.

**11. Record** (controller, `remediation_record`). One outcome is appended to
`outcomes.jsonl`. A `success` copies the playbook into `index/`, which makes it
reference material for stage 5 on any host.

| Approval | Confirmation | Signature changed | Health check | Recorded as | Indexed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `yes` | `yes` | yes | passed | `success` | yes |
| `yes` | `yes` | no | not run | `failed` | no |
| `yes` | `yes` | yes | failed | `failed` | no |
| `yes` | anything else | — | — | `unconfirmed` | no |
| anything else | — | — | — | nothing; the run stops | no |

## Reading the output

Stages 1 to 6 print one line per step while the task runs. On a colour
terminal the host name is a purple badge, and a mark shows the state:

```
 tinybot  · not running: ollama
 tinybot  › diagnosing with openrouter/deepseek/deepseek-v4-flash …
 tinybot  ✓ diagnosing with openrouter/deepseek/deepseek-v4-flash 12s
 tinybot  · diagnosis: podman:container_state_exited+shm_mount_einval, service ollama, severity high
 tinybot  · recording the incident and embedding its summary
 tinybot  · incident inc-dfc1e47fdb5f: 4 similar past incidents, best score 0.89
 tinybot  · no template matches; drafting a playbook with the model, 0 past remediations as reference
 tinybot  › drafting …
 tinybot  ✓ drafting 48s
 tinybot  · checking the draft for volume removal and unproven container removal
 tinybot  ✗ rejected outage guard: task 'Remove existing ollama container' removes container ollama before ...
```

| Mark | Meaning |
| :--- | :--- |
| `›` | A step has started. |
| `✓` | A step finished; the dim number is its duration. |
| `✗` | A step failed, or the draft was rejected. |
| `!` | A host warning from the health gate. |
| `·` | Information. |

A healthy host prints one line and the run ends:

```
 tinybot  ✓ healthy: 8 of 8 containers running, 1 pods running; nothing to remediate
```

When output is not a terminal, or `NO_COLOR` is set, or Ansible colour is off,
the same events print as plain ASCII words for logs, CI and screen readers:

```
tinybot: drafting, started
tinybot: drafting, done in 48s
tinybot: warning, SELinux is disabled by the selinux=0 boot argument although /etc/selinux/config says enforcing
tinybot: rejected, outage guard: task 'Remove existing ollama container' removes container ollama ...
```

## Guards

A draft passes five checks before you see it. The first failure writes the
draft to `playbooks/rejected/<id>.yml` and the reasons to
`playbooks/rejected/<id>.reason.json`, and the play stops with those reasons.

**1. Parse.** The draft must be a YAML mapping or list. A markdown code fence
around it is stripped first.

**2. Volume guard** (`remediation_guard.scan_playbook`). Rejects any draft that
removes a Podman volume or the data under one:

- `podman volume rm`, `podman volume prune`, `podman system reset`
- `podman system prune --volumes`
- `podman rm`, `podman container rm` or `podman pod rm` with `-v` or
  `--volumes`, including combined short flags such as `-fv`
- `podman compose down -v` and `podman-compose down --volumes`
- `containers.podman.podman_volume` with `state: absent`
- `containers.podman.podman_prune` with `volume: true` or `system_volumes: true`
- `rm`, `find -delete` or `ansible.builtin.file: state=absent` on
  `…/containers/storage/volumes`, or on any directory that contains it: `~`,
  `~/.local`, `~/.local/share`, `…/containers`, `…/containers/storage`,
  `/var/lib/containers`, `/`

Values from `vars:` and `set_fact` are substituted into `{{ name }}` before
matching. A deletion whose target still contains an unresolved template, such
as a loop item, cannot be proven safe and is rejected. Flags are matched per
pipeline stage, so `podman rm x && grep -v y` is not mistaken for a volume
removal. Container-internal paths such as
`overlay-containers/<id>/userdata/shm` are not volume data and pass.

**3. Outage guard** (`remediation_guard.scan_outage`). Rejects any draft that
removes or recreates a container or pod before an earlier task has test-run
the replacement image. Removal means `state: absent` or `recreate: true` on
`podman_container` or `podman_pod`, `podman rm`, `podman container rm`,
`podman pod rm`, or compose `down`. A test run is a `podman run --rm` command,
or a `podman_container` task with `rm: true`. Tasks are read in execution
order, including those inside `block`, `rescue` and `always`. The model is
taught this order, which passes:

1. `podman run --rm <image> --version`, with `changed_when: false`
2. `podman stop <name>`, then `podman rename <name> <name>-old`
3. create and start the new container with the original settings
4. check that it answers
5. remove `<name>-old`

This guard exists because of a real outage. On 2026-09-30 a draft deleted a
working `ollama` container, then failed to create the replacement, and the
service stayed down until someone rebuilt it by hand.

**4. Syntax check.** `ansible-playbook --syntax-check`, 60-second timeout.

**5. Lint.** `ansible-lint --profile production --nocolor`, 180-second timeout.

What the guards do **not** check: privileged host changes (`become` with
`sysctl`, packages, services or files outside volume storage), and anything
inside a role the draft calls. Read those tasks at the approval prompt.

## What the gather collects

| Section | Source | Notes |
| :--- | :--- | :--- |
| `host` | `/etc/os-release`, `uname -r`, `podman version`, `df -h`, `/proc/meminfo`, hostname | |
| `host_security` | `getenforce`, `/etc/selinux/config`, `/proc/cmdline`, `/sys/kernel/security/lsm`, `journalctl -k -b`, `last -x`, `loginctl show-user` | Kernel log lines are filtered to overlay, tmpfs, shm, SELinux, AVC, mount, EINVAL, EPERM and "not permitted"; last 50 kept. |
| `pods` | `podman pod ps`, `podman pod inspect` | |
| `containers` | `podman ps -a`, `podman inspect` | Filtered by the `pod` option when set. |
| `logs` | `podman logs --tail <log_lines>` per container | |
| `journal` | `journalctl --user` and system journal, `-u <journal_units>`, `--since <since>` | |
| `mounts` | `findmnt -J` | Filtered to shm, overlay and `/run/user`. |
| `selinux` | `ausearch -m AVC -ts recent` | Usually needs root; reported as unavailable otherwise. |

`host_security` is there because container errors often start on the host. On
2026-09-30 every image-based container on `tinybot` failed with
`failed to mount shm tmpfs: invalid argument` or
`creating /etc/mtab symlink: operation not permitted`. The cause was a
`selinux=0` boot argument. The evidence was one kernel log line,
`tmpfs: Unknown parameter 'context'`, which the gather did not collect at the
time. The model blamed the shared-memory size instead.

**Redaction.** Before the document leaves the host, the module replaces with
`REDACTED`:

- values under keys that match `pass`, `secret`, `key`, `token`, `salt` or `auth`
- `NAME=value` entries with such a name, in environment lists and in log and
  journal text
- the password in any `scheme://user:password@host` URL, such as `DATABASE_URL`

## Storage

Default root `~/.local/share/syncopated/remediation/`, set with
`REMEDIATION_STORE`.

```
incidents.jsonl                one record per diagnosis: id, host, created_at (UTC),
                               summary, signature, service, role, severity,
                               embedding model and vector
outcomes.jsonl                 one record per remediation attempt: incident id,
                               playbook path, result, confirmed_by, created_at
diagnostics/<id>.json          the redacted gather output behind each incident
playbooks/pending/<id>.yml     drafts that passed every guard
playbooks/rejected/<id>.yml    drafts a guard refused
playbooks/rejected/<id>.reason.json
index/<id>.yml                 confirmed successful remediations only
```

The JSONL files are the whole state. The DuckDB index is rebuilt in memory on
every search and never written to disk. The store grows with every diagnosis
on a failing host; healthy hosts add nothing. To start over, move the
directory aside.

## Configuration

Environment variables, read on the controller:

| Env | Default | Effect |
| :--- | :--- | :--- |
| `AI_PROVIDER`, `AI_MODEL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS` | `[callback_llm_analyzer]` in `ansible.cfg`, else `openrouter`, `openrouter/deepseek/deepseek-v4-flash`, `0.4`, `8192` | The environment overrides `ansible.cfg`, as for the `llm_analyzer` callback. |
| `<PROVIDER>_API_KEY` | — | For example `OPENROUTER_API_KEY`. |
| `OLLAMA_HOST` | `http://localhost:11434` | Embedding endpoint. |
| `REMEDIATION_STORE` | `~/.local/share/syncopated/remediation/` | Store root. |
| `REMEDIATION_SIMILARITY_THRESHOLD` | `0.80` | Minimum cosine score for a past remediation to be given to the model as reference. Uncalibrated. |
| `REMEDIATION_CONTEXT_BUDGET` | `24000` | Characters of diagnostics sent to the model. |
| `REMEDIATION_PYTHON` | `<repo>/.venv/bin/python` | Interpreter for the pipeline CLI. |
| `REMEDIATION_ANSIBLE_PLAYBOOK`, `REMEDIATION_ANSIBLE_LINT` | first on `PATH` | Tools used by guards 4 and 5. |
| `NO_COLOR` | unset | Any value switches progress output to plain words. |

Extra vars for `playbooks/remediate.yml`:

| Var | Default | Effect |
| :--- | :--- | :--- |
| `target` | — | Required. Host or group pattern. |
| `remediation_force` | `false` | Diagnose even when the health gate reports healthy. |
| `remediation_approve` | unset | `yes` answers the approval prompt. Only the string `yes` counts. |
| `remediation_confirm` | unset | `yes` answers the confirmation prompt. |
| `remediation_inventory` | `inventory/hosts.yml` | Inventory for the approved playbook. Not taken from your `-i`. |

For an unattended run you must opt in to both prompts:

```bash
ansible-playbook playbooks/remediate.yml -e target=tinybot \
  -e remediation_approve=yes -e remediation_confirm=yes
```

`--check` runs the read-only gather and the health gate, then ends.

## Plugin reference

### remediation_diagnose

| Option | Default | Notes |
| :--- | :--- | :--- |
| `pod` | all | Limit containers to one pod. Forwarded to the gather. |
| `log_lines` | `200` | Forwarded to the gather. |
| `journal_units` | `["podman*", "conmon*", "user@*"]` | Forwarded to the gather. |
| `since` | `-1h` | Forwarded to the gather. |
| `force` | `false` | Skip the health gate. Not forwarded. |

Returns `status`: `healthy`, `generated` or `rejected`. Every result carries
`health` (the gate's verdict and evidence). `generated` and `rejected` also
carry `incident_id`, `tier`, `template_id`, `signature_version`, `summary`,
`error_signature`, `service`, `role`, `severity`, `matches`, `rationale`,
`health_check` and `playbook_path`. `generated` adds `playbook_yaml`;
`rejected` adds `rejected_reasons`. `changed` is always false.

### remediation_verify

Takes `diagnostics` (the registered output of a `remediation_gather` task) and
`error_signature`. Returns `resolved`, `new_signature`, `old_signature` and
`summary`.

### remediation_record

Takes `incident_id`, `playbook_path`, `result` (`success`, `failed` or
`unconfirmed`) and optionally `confirmed_by`. Returns `indexed`. Reports
`changed: true`, since it writes to the store.

### remediation_gather

Options `pod`, `log_lines`, `journal_units` and `since`, as above. Returns
`diagnostics` with the sections listed in
[What the gather collects](#what-the-gather-collects). `changed` is always
false.

## Process boundaries

The action plugins run inside the `ansible-playbook` process. That interpreter
cannot import `dspy` or `duckdb`, so the plugins import only the standard
library and Ansible. They start `.venv/bin/python
plugins/callback_utils/remediation_cli.py <diagnose|verify|record>` as a child
process, write one JSON document to its stdin and read one from its stdout.
The child reports progress on stderr, one JSON event per line with the prefix
`REMEDIATION_PROGRESS`; the plugins print each event as it arrives.

| Module in `callback_utils/` | Imported by | Responsibility |
| :--- | :--- | :--- |
| `remediation_bridge.py` | action plugins | Runs the CLI, streams progress events, parses the result. |
| `remediation_health.py` | diagnose action, CLI | Health gate and the journal history split. No model. |
| `remediation_style.py` | action plugins | Renders progress events, styled or plain. |
| `remediation_cli.py` | — (child process) | Provider setup, both model calls, store access, guards. |
| `remediation_signatures.py` | CLI | DSPy signatures, `SIGNATURE_VERSION`, diagnostics trimming. |
| `remediation_store.py` | CLI | JSONL store, Ollama embeddings, DuckDB search. |
| `remediation_guard.py` | CLI | Volume guard and outage guard. |
| `remediation_templates.py` | CLI | Hand-written remediations for known signatures. |

CLI exit codes: `2` bad input, `3` provider unusable or a model call failed,
`4` Ollama unreachable or search failed, `5` internal error while recording.

## Known limitations

- **Verification compares signature strings.** The model spells one failure
  several ways (`pod_exited`, `pod_state_exited`), so a host that is still
  broken can read as resolved. The health check and your confirmation are the
  real safeguards.
- **A failed remediation run is not recorded.** If the approved playbook exits
  non-zero, the play stops before stage 11. Record it by hand with
  `remediation_cli.py record` and `result: failed`.
- **One missing container among several looks healthy.** The gate has no list
  of expected services. It only catches a host with no containers at all.
- **Privileged host changes are not guarded.** See [Guards](#guards).
- **The `langfuse_pod_exited` template is wrong for its known incidents.** It
  blames damaged image layers; the 2026-09-30 incidents were caused by SELinux
  being off. Its force-recreate also passes the role's placeholder secrets. Do
  not approve it unchanged.
- **`confirmed_by` is always `human`.** The play does not gather facts.
- **The similarity threshold is a guess** and needs calibration against real
  incidents.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Ends after *Report a healthy host* | Every container and pod is running | Nothing to do. Use `-e remediation_force=true` to diagnose anyway. |
| `remediation venv interpreter not found` | `.venv` missing | Run `bin/setup`, or set `REMEDIATION_PYTHON`. |
| `LLM provider ... is not usable` (exit 3) | Key missing or provider unreachable | Set `<PROVIDER>_API_KEY`; check `AI_PROVIDER` and `AI_MODEL`. |
| An error naming Ollama (exit 4) | Ollama down or model not pulled | `ollama serve`; `ollama pull embeddinggemma:latest`. |
| `rejected, volume guard: ...` or `rejected, outage guard: ...` | The draft failed a safety check | Run again for a new draft. Reasons are in `playbooks/rejected/<id>.reason.json`. |
| `rejected, ansible-lint failed` | The draft did not lint | Run again. |
| Stops at *Abort without approval* without a prompt | No terminal attached | Run from a terminal, or pass `-e remediation_approve=yes`. |
| Mount errors: `invalid argument`, `operation not permitted` | Often SELinux off via `selinux=0` | Look for the `!` warning line. Check `getenforce`, `cat /proc/cmdline`, `journalctl -k -b \| grep context`. |

## Tests

```bash
.venv/bin/python -m pytest tests -q                  # 159 tests; no network needed
.venv/bin/python -m pytest tests -q -m ollama        # only the live-Ollama test
ansible-lint --profile production plugins/ playbooks/remediate.yml
```

The live-Ollama test skips itself when no daemon is listening on
`localhost:11434` or `embeddinggemma:latest` is not pulled.

The playbook tests run `remediate.yml` against localhost with the CLI replaced
by a stub. They pass `remediation_force=true` so that the containers on the
machine running the tests do not decide the result.
