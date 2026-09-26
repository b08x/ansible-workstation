# b08x.llmops.langfuse

> Authored by Mistral Vibe (GLM-5.2) — this role was built, debugged, and
> verified end-to-end through an interactive agent session. Every task file,
> template, and argument spec was written from scratch, tested against a live
> Podman daemon, and iterated on when containers misbehaved. What follows is
> the role documentation written from that first-hand experience.

Deploys self-hosted [Langfuse v4](https://langfuse.com) — the open-source LLM
observability platform — as a six-container stack with PostgreSQL, ClickHouse,
Redis, and MinIO. Supports two container runtimes selected by a single variable.

## What This Role Does

```
tasks/main.yml
  ├── Create deploy directory + render .env file
  ├── include_tasks: docker.yml   (when langfuse_container_runtime == "docker")
  ├── include_tasks: podman.yml   (when langfuse_container_runtime == "podman")
  └── include_tasks: backup.yml   (when langfuse_backup_action != "none")
```

### Docker Compose path (`tasks/docker.yml`)

Renders `docker-compose.yml.j2` into the deploy directory, pulls images, and
brings the stack up via `community.docker.docker_compose_v2`. Each service gets
its own network namespace and is reached by service hostname (e.g.
`postgres:5432`).

### Podman path (`tasks/podman.yml`)

Builds the stack with `containers.podman` modules — five named volumes, one
pod, and six containers. All containers share the pod's network namespace and
communicate via `localhost`. The pod publishes ports on the host.

Lessons learned during development that are baked into the task file:

- **No `hostname:` on pod containers.** Podman pods own the UTS namespace;
  setting `hostname` on individual containers causes exit code 125 with
  "cannot set hostname when joining the pod UTS namespace."
- **MinIO `command` in list form.** String-form commands with nested single
  quotes get split on whitespace by podman before reaching the shell, causing
  "unexpected EOF while looking for matching `'`". List form passes clean argv
  tokens to `sh -c`.

### Backup/restore path (`tasks/backup.yml`)

Runs `pg_dump` / `pg_restore` inside the postgres container via `docker exec`
or `podman exec` — no host-side postgresql-client required. The container CLI
is selected automatically based on `langfuse_container_runtime`. The container
name (`{{ langfuse_project_name }}-postgres`) is consistent across both
runtimes.

```
backup_action=backup  →  pg_dump with timestamp + retention pruning
backup_action=restore →  file validation + pg_restore (custom) or psql (plain)
backup_action=none    →  entire include skipped
```

## Requirements

- **Docker path:** Docker Engine with Compose plugin + `community.docker` collection
- **Podman path:** Podman installed + `containers.podman` collection
- The target host should have the `user.home` fact available (from group vars
  or `ansible_facts`), or set `langfuse_deploy_dir` explicitly

## Role Variables

All variables use the `langfuse_` prefix. Defined in `defaults/main.yml`.

### Runtime & Deployment

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_container_runtime` | `docker` | Runtime: `docker` or `podman` |
| `langfuse_deploy_dir` | `{{ user.home }}/langfuse` | Deploy directory for files and data |
| `langfuse_project_name` | `langfuse` | Compose project name / pod name |

### Images

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_image_tag` | `latest` | Langfuse web/worker image tag |
| `langfuse_clickhouse_image_tag` | `25.12` | ClickHouse server image tag |
| `langfuse_postgres_version` | `17` | PostgreSQL major version |

### Ports and Firewall

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_web_port` | `3000` | Host port for Langfuse web UI |
| `langfuse_worker_port` | `3030` | Host port for Langfuse worker |
| `langfuse_minio_api_port` | `9090` | Host port for MinIO S3 API |
| `langfuse_minio_console_port` | `9091` | Host port for MinIO console |
| `langfuse_bind_localhost` | `true` | Bind infra ports to 127.0.0.1 only |
| `langfuse_firewall_ports` | `[web, worker, minio ports]` | Firewall ports to open when `langfuse_bind_localhost` is false |
| `langfuse_force_recreate` | `false` | Force container recreation on every run |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `langfuse_telemetry_enabled` | `true` | Enable anonymous telemetry |
| `langfuse_enable_experimental_features` | `false` | Enable experimental features |

### Secrets

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_nextauth_url` | `http://localhost:3000` | Public URL for NextAuth |
| `langfuse_nextauth_secret` | `mysecret` | NextAuth JWT secret |
| `langfuse_salt` | `mysalt` | Salt for API key hashing |
| `langfuse_encryption_key` | `0000...` | 32-byte hex key (`openssl rand -hex 32`) |
| `langfuse_postgres_user` | `postgres` | PostgreSQL user |
| `langfuse_postgres_password` | `postgres` | PostgreSQL password |
| `langfuse_postgres_db` | `postgres` | PostgreSQL database name |
| `langfuse_clickhouse_user` | `clickhouse` | ClickHouse user |
| `langfuse_clickhouse_password` | `clickhouse` | ClickHouse password |
| `langfuse_redis_auth` | `myredissecret` | Redis password |
| `langfuse_minio_root_user` | `minio` | MinIO root user |
| `langfuse_minio_root_password` | `miniosecret` | MinIO root password |

### Storage

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_s3_event_upload_bucket` | `langfuse` | S3 bucket for event uploads |
| `langfuse_s3_media_upload_bucket` | `langfuse` | S3 bucket for media uploads |
| `langfuse_s3_batch_export_bucket` | `langfuse` | S3 bucket for batch exports |

### ClickHouse Cluster

| Variable | Default | Description |
|----------|---------|-------------|
| `langfuse_clickhouse_cluster_enabled` | `false` | Enable cluster mode |
| `langfuse_clickhouse_cluster_name` | `default` | Cluster name |

### Backup/Restore

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `langfuse_backup_action` | `none` | `none`, `backup`, or `restore` |
| `langfuse_backup_dir` | `{{ langfuse_deploy_dir }}/backups` | Backup directory |
| `langfuse_backup_file` | `""` | Restore source file (.dump or .sql) |
| `langfuse_backup_format` | `custom` | `custom` (-Fc, pg_restore) or `plain` (-Fp, psql) |
| `langfuse_backup_compression` | `6` | Compression level 0-9 (custom format only) |
| `langfuse_backup_retention_days` | `7` | Days to retain backups before pruning |

> **Note:** Langfuse backup is PostgreSQL-only. Unlike the Dify role, there is
> no volume backup — ClickHouse and MinIO data are not included. For full
> disaster recovery, back up MinIO buckets and ClickHouse data separately.

## Dependencies

None.

## Example Playbooks

### Docker Compose (default)

```yaml
- name: Deploy Langfuse via Docker Compose
  hosts: workstations
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: docker
        langfuse_nextauth_url: "http://langfuse.example.com:3000"
        langfuse_nextauth_secret: "{{ vault_langfuse_nextauth_secret }}"
        langfuse_encryption_key: "{{ vault_langfuse_encryption_key }}"
        langfuse_postgres_password: "{{ vault_langfuse_postgres_password }}"
        langfuse_clickhouse_password: "{{ vault_langfuse_clickhouse_password }}"
        langfuse_redis_auth: "{{ vault_langfuse_redis_auth }}"
        langfuse_minio_root_password: "{{ vault_langfuse_minio_root_password }}"
```

### Podman (rootless, single host)

```yaml
- name: Deploy Langfuse via Podman
  hosts: tinybot
  become: false
  gather_facts: true
  vars:
    langfuse_container_runtime: podman
    langfuse_deploy_dir: "{{ user.home }}/LLMOS/langfuse"
  roles:
    - role: b08x.llmops.langfuse
      tags: ["langfuse", "llmops"]
```

### Backup

```yaml
- name: Backup Langfuse PostgreSQL
  hosts: tinybot
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: podman
        langfuse_backup_action: backup
```

### Restore

```yaml
- name: Restore Langfuse PostgreSQL
  hosts: tinybot
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: podman
        langfuse_backup_action: restore
        langfuse_backup_file: "/home/b08x/LLMOS/langfuse/backups/postgres_20260904T120000.dump"
```

## Runtime Comparison

| Aspect | Docker | Podman |
| -------- | -------- | -------- |
| Module | `community.docker.docker_compose_v2` | `containers.podman.*` |
| Network | Service hostnames (e.g. `postgres:5432`) | `localhost` (shared pod namespace) |
| Stack definition | `docker-compose.yml` template | Individual volume/pod/container tasks |
| Container names | Set by compose service + `container_name` | Set explicitly per container |
| Backup CLI | `docker exec` | `podman exec` |

## Idempotency

Both runtime paths are idempotent. Re-running the role reconciles the stack
to the desired state — volumes, pod, and containers are created if absent,
updated if configuration changed, and left alone if already correct.

## Rollback

Reverting the compose/env templates and re-running will restore the previous
state. Named volumes (PostgreSQL, ClickHouse, MinIO, Redis) persist
independently and survive container recreation.

## Argument Specification

See `meta/argument_specs.yml` for the full argument spec with types, choices,
and defaults for all 30+ variables.

## Container Stack

| Service | Image | Port | Purpose |
| --------- | ------- | ------ | --------- |
| `langfuse-web` | `langfuse/langfuse:latest` | 3000 | Web UI (Next.js) |
| `langfuse-worker` | `langfuse/langfuse:latest` | 3030 | Background worker (BullMQ) |
| `postgres` | `postgres:17` | 5432 | Primary database |
| `clickhouse` | `clickhouse/clickhouse-server:25.12` | 8123, 9000 | Analytics store (event ingestion) |
| `redis` | `redis:7-alpine` | 6379 | Queue backend (BullMQ) |
| `minio` | `minio/minio:latest` | 9000, 9091 | S3-compatible object storage |

### Named Volumes

| Volume | Purpose |
| -------- | --------- |
| `langfuse_postgres_data` | PostgreSQL data |
| `langfuse_clickhouse_data` | ClickHouse data |
| `langfuse_clickhouse_logs` | ClickHouse logs |
| `langfuse_minio_data` | MinIO object storage |
| `langfuse_redis_data` | Redis persistence |

## Usage Guide

### 1. Generate Secrets

Before deploying, generate the required secrets. Never use the defaults in
production.

```bash
# NextAuth secret (JWT signing)
openssl rand -hex 32

# Encryption key (sensitive data at rest — must be exactly 64 hex chars)
openssl rand -hex 32

# Salt (API key hashing)
openssl rand -hex 16
```

Store these in an Ansible Vault or your secrets manager:

```yaml
# group_vars/langfuse.yml (vault-encrypted)
vault_langfuse_nextauth_secret: "abc123..."
vault_langfuse_encryption_key: "def456..."
vault_langfuse_salt: "ghi789..."
vault_langfuse_postgres_password: "strong_pg_password"
vault_langfuse_clickhouse_password: "strong_ch_password"
vault_langfuse_redis_auth: "strong_redis_password"
vault_langfuse_minio_root_password: "strong_minio_password"
```

### 2. Deploy with Docker Compose

The default runtime. Requires Docker Engine with the Compose plugin and the
`community.docker` Ansible collection.

```yaml
- name: Deploy Langfuse via Docker Compose
  hosts: langfuse_hosts
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: docker
        langfuse_deploy_dir: "/opt/langfuse"
        langfuse_nextauth_url: "http://langfuse.example.com:3000"
        langfuse_nextauth_secret: "{{ vault_langfuse_nextauth_secret }}"
        langfuse_encryption_key: "{{ vault_langfuse_encryption_key }}"
        langfuse_salt: "{{ vault_langfuse_salt }}"
        langfuse_postgres_password: "{{ vault_langfuse_postgres_password }}"
        langfuse_clickhouse_password: "{{ vault_langfuse_clickhouse_password }}"
        langfuse_redis_auth: "{{ vault_langfuse_redis_auth }}"
        langfuse_minio_root_password: "{{ vault_langfuse_minio_root_password }}"
```

```bash
ansible-playbook deploy-langfuse.yml
```

Docker Compose uses service hostnames for inter-container networking —
postgres is reached at `postgres:5432`, clickhouse at `clickhouse:8123`, etc.
This is handled by the compose template automatically.

### 3. Deploy with Podman (Rootless)

Rootless podman runs without `become: true`. Requires the `containers.podman`
Ansible collection.

```yaml
- name: Deploy Langfuse via Podman
  hosts: tinybot
  become: false
  gather_facts: true
  vars:
    langfuse_container_runtime: podman
    langfuse_deploy_dir: "{{ user.home }}/LLMOS/langfuse"
    langfuse_nextauth_url: "http://tinybot:3000"
    langfuse_bind_localhost: false
  roles:
    - role: b08x.llmops.langfuse
      tags: ["langfuse", "llmops"]
```

```bash
ansible-playbook langfuse-podman-tinybot.yml
```

Podman uses a pod — all containers share the network namespace and
communicate via `localhost`. The pod publishes ports on the host.

**External access:** Set `langfuse_bind_localhost: false` to publish ports on
`0.0.0.0` so Langfuse is reachable from other hosts via the hostname. With
`true` (default), ports bind to `127.0.0.1` only — local access works,
remote access is refused.

### 4. Update Configuration

Change a variable in the playbook and re-run. The behavior depends on the
runtime:

- **Docker:** The `.env` template change notifies the "Restart Langfuse stack"
  handler, which runs `docker_compose_v2` with `recreate: always`. All
  containers are recreated with the new environment.
- **Podman:** The `podman_container` module detects env dict changes and
  recreates the affected container automatically. No handler fires for
  podman — the module's own idempotency check handles it.

### 5. Backup the Database

Run the role with `langfuse_backup_action: backup`. This executes `pg_dump`
inside the postgres container — no host-side postgresql-client needed.

```yaml
- name: Backup Langfuse PostgreSQL
  hosts: tinybot
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: podman
        langfuse_backup_action: backup
```

```bash
ansible-playbook backup-langfuse.yml
```

Backups are written to `{{ langfuse_backup_dir }}` (default:
`{{ langfuse_deploy_dir }}/backups`) with timestamped filenames:

```
postgres_20260904T143000.dump   (custom format, compressed)
postgres_20260904T143000.sql   (plain SQL)
```

Old backups beyond `langfuse_backup_retention_days` (default: 7) are pruned
automatically.

**What's included:** PostgreSQL database only (traces, users, projects, API keys).

**What's NOT included:** ClickHouse analytics data, MinIO object storage (media,
event uploads, batch exports). For full disaster recovery, back up these
separately:

```bash
# MinIO backup (run on the MinIO host)
mc mirror minio/langfuse /backup/langfuse-minio/

# ClickHouse backup (run on the ClickHouse host)
clickhouse-client --query "BACKUP TABLE default TO Disk('backups', 'langfuse-ch')"
```

### 6. Restore the Database

Provide a backup file path and set the action to `restore`.

```yaml
- name: Restore Langfuse PostgreSQL
  hosts: tinybot
  become: false
  roles:
    - role: b08x.llmops.langfuse
      vars:
        langfuse_container_runtime: podman
        langfuse_backup_action: restore
        langfuse_backup_file: "/home/b08x/LLMOS/langfuse/backups/postgres_20260904T143000.dump"
```

```bash
ansible-playbook restore-langfuse.yml
```

The role validates the file exists before attempting restore. Custom format
(`.dump`) uses `pg_restore --clean --if-exists`; plain SQL (`.sql`) is piped
through `psql`.

### 7. Tear Down

To remove the entire stack:

```bash
# Podman
podman pod stop langfuse && podman pod rm langfuse
podman volume rm langfuse_postgres_data langfuse_clickhouse_data \
  langfuse_clickhouse_logs langfuse_minio_data langfuse_redis_data

# Docker
docker compose -f /opt/langfuse/docker-compose.yml down -v
```

Named volumes persist independently. Removing containers does not destroy
data unless volumes are explicitly removed.

## Troubleshooting

### Container can't reach postgres at localhost:5432 (Podman)

If containers are individually recreated (e.g. by env var changes), rootless
podman with netavark may assign them to different network namespaces despite
being in the same pod. Symptoms:

```
Error: P1001: Can't reach database server at `localhost:5432`
```

Verify all containers share the same network namespace:

```bash
for c in langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio \
         langfuse-worker langfuse-web; do
  pid=$(podman inspect "$c" --format '{{.State.Pid}}')
  echo "$c: $(ls -l /proc/$pid/ns/net | awk -F'->' '{print $2}')"
done
```

If namespaces differ, recreate the entire pod atomically:

```bash
podman pod stop langfuse && podman pod rm langfuse
ansible-playbook langfuse-podman-tinybot.yml
```

### `http://hostname:3000` connection refused

`langfuse_bind_localhost: true` (default) binds all ports to `127.0.0.1`. For
external access, set `langfuse_bind_localhost: false` in the playbook. The
Next.js startup banner showing `http://langfuse:3000` is cosmetic — it uses
`os.hostname()`, not `NEXTAUTH_URL`.

### Podman handler errors on env change

If you see "Address already in use" or "container state improper" when
re-running after changing env vars, this was a handler conflict that has
been fixed. The handler now only fires for the Docker runtime. Podman relies
on `podman_container`'s native env diff detection for recreation.

### MinIO container exits with EOF quoting error

This was caused by string-form `command` with nested quotes being split on
whitespace by podman. The role now uses list-form `command` for MinIO. If
you encounter this in a fork, ensure the command is a YAML list:

```yaml
command:
  - "-c"
  - "mkdir -p /data/langfuse && minio server --address ':9000' --console-address ':9001' /data"
```

### Podman containers fail with hostname error

Setting `hostname:` on containers in a pod causes exit code 125 — pods own
the UTS namespace. The role no longer sets `hostname:` on pod containers.

## License

GPL-2.0-or-later

## Author Information

Authored by Mistral Vibe (GLM-5.2) — an AI coding agent by Mistral AI.
Built and verified against a live Podman deployment on a RHEL workstation.
