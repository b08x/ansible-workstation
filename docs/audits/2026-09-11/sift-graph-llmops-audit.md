# SIFT-Graph Report: b08x.llmops collection — roles/tasks structure & correctness audit

**Generated**: 2026-09-11
**Project**: home-b08x-WorkspaceV3-Syncopated-ansible-collections-b08x-llmops
**Graph Status**: indexed (654 nodes, 860 edges, moderate mode)
**Producer**: sift-graph v0.1 (skill) + ansible-patterns-anti-patterns audit lens
**Lint verification**: ansible-lint production profile — Passed: 0 failure(s), 0 warning(s) in 62 files processed of 91 encountered
**Sidecar**: sift-graph-llmops-audit.sift-graph.json (machine-readable provenance, 32 claims)

Provenance shorthand: `[Graph:Type](qualified_name:lines)` resolves to the indexed knowledge graph.

---

## 1. ✅ Verified Facts

| Statement | Status | Provenance | Confidence |
|---|---|---|---|
| Collection has 6 roles: dify, hermes, langfuse, ollama, run, tts | ✅ | [Graph:Folder](home-b08x-WorkspaceV3-Syncopated-ansible-collections-b08x-llmops.roles:roles) | 5 |
| dify/tasks/main.yml is a dispatcher: debug entry → runtime pre-flight → dir creation → config deploy → runtime-specific include (docker.yml/podman.yml) → firewall → backup include | ✅ | [Graph:Module](roles.dify.tasks.main:1-183) | 5 |
| dify pre-flight verifies runtime via `<runtime> --version` with failed_when:false + register, then fail if rc != 0 (patterns 5/9) | ✅ | [Graph:Module](roles.dify.tasks.main:9-24) | 5 |
| langfuse/tasks/main.yml mirrors the identical pre-flight + dispatcher structure with langfuse_-prefixed vars | ✅ | [Graph:Module](roles.langfuse.tasks.main:1-68) | 5 |
| dify docker.yml: template compose (backup:true, notify) → `docker compose pull` → docker_compose_v2 present/pull always — full lifecycle (pattern 4, Tier Full) | ✅ | [Graph:Module](roles.dify.tasks.docker:1-28) | 5 |
| dify podman.yml uses `podman compose` CLI: template → optional `down` (force_recreate) → pull → `up -d` | ✅ | [Graph:Module](roles.dify.tasks.podman:1-35) | 5 |
| langfuse podman.yml instead uses containers.podman modules (podman_pod + podman_volume + podman_container) with healthchecks and a rescue block | ✅ | [Graph:Module](roles.langfuse.tasks.podman:1-284) | 5 |
| Firewall tasks in both roles are variable-driven (`loop: {{ *_firewall_ports }}`, gated on `not (*_bind_localhost | bool)`) — pattern 15 clean | ✅ | [Graph:Module](roles.dify.tasks.main:166-177) | 5 |
| Both "Restart * stack" handlers are docker-only (`when: *_container_runtime == "docker"`) with comments explaining podman needs no handler — not dead handlers | ✅ | [Graph:Module](roles.dify.handlers.main:1-17) | 5 |
| defaults/vars separation correct in both real roles: overridable config in defaults/main.yml (dify 117 lines, langfuse 87), internal image refs + derived paths only in vars/main.yml | ✅ | [Graph:Variable](roles.dify.defaults.main:1-117), [Graph:Variable](roles.dify.vars.main:1-22) | 5 |
| Feature-flag dialect is uniform within each real role (`var | bool`); no dialect mixing inside a role | ✅ | [Graph:Module](roles.dify.tasks.podman:14-34) | 4 |
| Every include/import and config task carries explicit tags [role, subsystem] — tag-as-select applied | ✅ | [Graph:Module](roles.dify.tasks.main:156-164) | 5 |
| dify argument_specs.yml fully types the interface: choices for runtime, int ports, bool flags, 206 lines | ✅ | [Graph:Module](roles.dify.meta.argument_specs:1-207) | 5 |
| ansible-lint production profile passes for all roles: 0 failures, 0 warnings | ✅ | terminal run of .venv/bin/ansible-lint (62/91 files) — anchored [Graph:File](roles:1) | 5 |
| Only sample plugins ship (action/filter/lookup/module/test); extensions/eda + molecule scenarios are scaffold-grade | ✅ | [Graph:Class](plugins.action.sample_action.ActionModule:22-86) | 4 |

## 2. ⚠️ Errors & Corrections

| Statement | Status | Provenance | Confidence |
|---|---|---|---|
| Static-SIFT-era claims of "hardcoded firewall ports" and "dead reload firewalld handler" (from the pop_os-workstation-builder llmops playbook) do NOT apply to this collection — ports are variable-driven and the only handler is notified | ⚠️ corrected | [Graph:Module](roles.dify.tasks.main:166-177) | 5 |
| The indexer flags roles/*/templates/*.j2 as parse_partial (dify compose 410 lines, dify env.j2 170, langfuse compose 163, langfuse env.j2 75) — behavioral claims about those templates were NOT deep-audited and must not be inferred from graph data alone | ⚠️ coverage gap | [Graph:Module](roles.dify.templates.docker-compose.yml.j2:1-410) | 4 |

## 3. 🚩 Findings (structure/correctness issues found)

| Finding | Severity | Provenance | Confidence |
|---|---|---|---|
| roles/tts is misnamed inside: tasks header says `b08x.llmops.whisper` and its variable is `whisper_my_variable` while the directory is tts | minor bug | [Graph:Module](roles.tts.tasks.main:1-7) | 5 |
| Scaffold roles hermes/ollama/run/tts are unmodified ansible-creator stubs (6-line debug task, demo argument_specs) shipped in a Galaxy-published collection | structural debt | [Graph:Module](roles.hermes.tasks.main:1-7), [Graph:Module](roles.run.meta.argument_specs:1-12) | 5 |
| Plaintext demo secrets ship as role defaults: langfuse nextauth_secret "mysecret", salt "mysalt", redis/minio passwords, all-zero encryption_key | security | [Graph:Variable](roles.langfuse.defaults.main.langfuse_nextauth_secret:45-49) | 5 |
| dify defaults ship upstream demo secrets: db/redis/pgvector password `difyai123456`, literal plugin-daemon + agent tokens, weaviate API key | security | [Graph:Variable](roles.dify.defaults.main.dify_plugin_daemon_key:54-75) | 5 |
| dify backup: `creates:` guard on a timestamped filename means the pg_dump effectively always runs (idempotency is cosmetic) | minor | [Graph:Module](roles.dify.tasks.backup:46-76) | 4 |
| dify "Restart Dify stack" handler pins pull: always + recreate: always — any config change re-pulls and recreates the entire stack | performance | [Graph:Module](roles.dify.handlers.main:7-16) | 4 |

## 4. 🔍 Potential Leads

| Lead | Provenance | Confidence |
|---|---|---|
| `dify_backup_container` is hard-coded to compose default naming `{{ dify_project_name }}-db_postgres-1`; compose service renames silently break backup exec | [Graph:Module](roles.dify.tasks.backup:8-12) | 4 |
| langfuse podman rescue block only prints a debug msg — it swallows `ansible_failed_task` detail; should re-raise or fail with context | [Graph:Module](roles.langfuse.tasks.podman:281-284) | 4 |
| Scaffold roles should be implemented against the dify/langfuse skeleton or removed before a Galaxy release | [Graph:Module](roles.run.meta.argument_specs:1-12) | 4 |
| langfuse podman path publishes infra ports (5432/8123/9000/6379) in the pod while the defaults comment promises they "stay localhost-bound" — true only because publish prefixes 127.0.0.1 when bind_localhost is true; verify intent if bind_localhost=false | [Graph:Module](roles.langfuse.tasks.podman:63-76) | 3 |

## 5. ❓ Unable to Substantiate

| Claim | Why | Provenance | Confidence |
|---|---|---|---|
| Backup/restore volume-tarball path (backup.yml lines 81-233) is symmetric and correct | not fully read this run; only first 80 lines verified | [Graph:Module](roles.dify.tasks.backup:81-233) | 2 |
| docker-compose.yml.j2 templates reference every vars/main.yml image name correctly | parse_partial flagged by indexer; not read line-by-line | [Graph:Module](roles.langfuse.templates.docker-compose.yml.j2:1-163) | 2 |

## 6. 💡 Recommendations

1. Adopt the dify/langfuse skeleton (debug entry → pre-flight → dispatcher → runtime include → tagged tasks → variable-driven firewall → backup include) as the canonical role pattern for this collection; promote or delete the four scaffold roles. [C31]
2. Fix tts naming: either `whisper_*` → `tts_*` (vars, argument_specs, task header) or rename the directory to whisper. [C32]
3. Derive the backup container name from the compose template instead of hardcoding `*-db_postgres-1`, or look it up with `docker/podman ps --filter`. [C25]
4. Replace the langfuse rescue debug with `ansible.builtin.fail: msg: "{{ ansible_failed_task }}"` (or drop rescue entirely). [C27]
5. Move demo secrets out of defaults into vault/lookup-required variables (keep empty defaults + validation fail like dify_secret_key already does). [C17/C18]
6. Handler polish: drop `pull: always` from the restart handler (the pull step is already a separate task) to cut handler latency. [C20]

## 7. 🧪 Verification Steps Performed

- Indexed the collection into codebase-memory (654 nodes / 860 edges, moderate mode) and paged all 654 nodes via search_graph.
- Checked coverage via index_status flags: 5 parse_partial template/ini files identified and treated as evidence gaps, not silently trusted.
- Read every role's tasks/main.yml, both real roles' docker/podman/backup subtask files, both handlers, both defaults/vars, and dify argument_specs.
- Ran ansible-lint (production profile) over roles/: 0 failures, 0 warnings — real execution, not asserted.

## 8. 📚 Sources

- Graph: project home-b08x-WorkspaceV3-Syncopated-ansible-collections-b08x-llmops (this run's index)
- Skill: ansible-patterns-anti-patterns (15-pattern audit lens + verification checklist)
- Terminal: `.venv/bin/ansible-lint collections/ansible_collections/b08x/llmops/roles` → Passed (production profile)
- Machine-readable sidecar: `sift-graph-llmops-audit.sift-graph.json`

---

## 9. 📊 SIFT-Graph Meta-Rubric Scores

| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Claim Provenance | 5 | 40% | 2.00 |
| Section Completeness | 5 | 25% | 1.25 |
| Severity Calibration | 4 | 20% | 0.80 |
| Self-Critique Payoff | 3 | 15% | 0.45 |
| **Raw Score** | | | **4.50** |
| Pitfall Penalty | | | -0.0 |
| **Final Score** | | | **4.5** |
| Chain Integrity | 3 | | (min of dimensions) |

**Essential Cap**: Not triggered (Claim Provenance ≥ 3)
**Status**: Strong — minor revisions suggested
