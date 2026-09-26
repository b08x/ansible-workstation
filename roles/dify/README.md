# b08x.llmops dify Role

Deploy self-hosted [Dify](https://dify.ai) — an open-source LLM application
platform — via Docker Compose or Podman Compose.

## Requirements

- Docker or Podman installed on the target host
- `community.docker` collection (for Docker Compose deployments)
- `ansible.posix` collection (for firewalld management)

## Role Variables

All variables are defined in `defaults/main.yml` and use the `dify_` prefix
(Tier 2 role scope). The `user.home` variable is consumed from `group_vars`
(Tier 1 host scope).

### Core

| Variable | Default | Description |
| --- | --- | --- |
| `dify_container_runtime` | `docker` | Container runtime: `docker` or `podman` |
| `dify_deploy_dir` | `{{ user.home }}/dify` | Deployment directory for compose files and data |
| `dify_project_name` | `dify` | Docker Compose project name |
| `dify_bind_localhost` | `true` | Bind ports to 127.0.0.1 only |
| `dify_force_recreate` | `false` | Force container recreation on every run |
| `dify_deploy_env` | `PRODUCTION` | Deployment environment label |
| `dify_log_level` | `INFO` | Log level for all Dify services |
| `dify_enable_collaboration_mode` | `true` | Enable WebSocket collaboration (api_websocket service) |

### Image Tags

| Variable | Default | Description |
| --- | --- | --- |
| `dify_image_tag` | `1.17.0` | Dify API, web, and agent image tag |
| `dify_sandbox_image_tag` | `0.2.15` | Code execution sandbox image tag |
| `dify_plugin_daemon_image_tag` | `0.6.10-local` | Plugin daemon image tag |
| `dify_postgres_version` | `15-alpine` | PostgreSQL image tag |
| `dify_redis_version` | `6-alpine` | Redis image tag |

### Ports and Firewall

| Variable | Default | Description |
| --- | --- | --- |
| `dify_nginx_port` | `80` | Host port for Nginx HTTP |
| `dify_nginx_ssl_port` | `443` | Host port for Nginx HTTPS |
| `dify_plugin_debugging_port` | `5003` | Host port for plugin debugging |
| `dify_firewall_ports` | `[nginx ports]` | Firewall ports to open when `dify_bind_localhost` is false |

### Service URLs

Leave empty to use defaults derived from Nginx ingress. Set these when running
behind a reverse proxy or on a non-standard setup.

| Variable | Default | Description |
| --- | --- | --- |
| `dify_console_api_url` | `""` | Console API external URL |
| `dify_console_web_url` | `""` | Console web external URL |
| `dify_service_api_url` | `""` | Service API external URL |
| `dify_app_api_url` | `""` | App API external URL |
| `dify_app_web_url` | `""` | App web external URL |

### Database and Redis

| Variable | Default | Description |
| --- | --- | --- |
| `dify_db_username` | `postgres` | PostgreSQL user |
| `dify_db_password` | `difyai123456` | PostgreSQL password |
| `dify_db_database` | `dify` | PostgreSQL database name |
| `dify_db_plugin_database` | `dify_plugin` | Plugin daemon database name |
| `dify_redis_password` | `difyai123456` | Redis password |

### Security

| Variable | Default | Description |
| --- | --- | --- |
| `dify_secret_key` | `""` | Leave empty to auto-generate a persistent key |
| `dify_init_password` | `""` | Initial admin password |
| `dify_sandbox_api_key` | `dify-sandbox` | Sandbox API key |
| `dify_plugin_daemon_key` | (see defaults) | Plugin daemon server key |
| `dify_plugin_dify_inner_api_key` | (see defaults) | Internal API key for plugin-to-API communication |
| `dify_agent_api_token` | (see defaults) | Agent backend API token |
| `dify_agent_server_secret_key` | (see defaults) | Agent server secret key |

### Nginx

| Variable | Default | Description |
| --- | --- | --- |
| `dify_nginx_server_name` | `_` | Nginx server_name directive |
| `dify_nginx_https_enabled` | `false` | Enable HTTPS with Let's Encrypt |

### SSRF Proxy

| Variable | Default | Description |
|---|---|---|
| `dify_ssrf_proxy_allow_private_ips` | `""` | Allow private IPs in SSRF proxy (set to `1` to enable) |

### Vector Store

The role supports two vector store backends, selected via `dify_vector_store`.
The active backend is activated through a Docker Compose profile of the same
name. The inactive backend's service is defined but not started.

| Variable | Default | Description |
|---|---|---|
| `dify_vector_store` | `weaviate` | Vector store backend: `weaviate` or `pgvector` |

#### Weaviate (default)

| Variable | Default | Description |
| --- | --- | --- |
| `dify_weaviate_image_tag` | `1.39.2` | Weaviate image tag |
| `dify_weaviate_api_key` | (see defaults) | Weaviate API key |

#### pgvector

Uses a separate PostgreSQL container with the pgvector extension
(`pgvector/pgvector:pg16`). This is distinct from `db_postgres` (the relational
database) — pgvector has its own container, data volume, and credentials.

| Variable | Default | Description |
| --- | --- | --- |
| `dify_pgvector_image_tag` | `pg16` | pgvector Docker image tag |
| `dify_pgvector_host` | `pgvector` | pgvector hostname (compose service name) |
| `dify_pgvector_port` | `5432` | pgvector port |
| `dify_pgvector_user` | `postgres` | pgvector PostgreSQL user |
| `dify_pgvector_password` | `difyai123456` | pgvector PostgreSQL password |
| `dify_pgvector_database` | `dify` | pgvector database name |
| `dify_pgvector_pgdata` | `/var/lib/postgresql/data/pgdata` | pgvector data directory |
| `dify_pgvector_min_connection` | `1` | Connection pool minimum |
| `dify_pgvector_max_connection` | `5` | Connection pool maximum |
| `dify_pgvector_pg_bigm` | `false` | Enable pg_bigm full-text search module |
| `dify_pgvector_pg_bigm_version` | `1.2-20240606` | pg_bigm module version |

### Backup/Restore

| Variable | Default | Description |
| --- | --- | --- |
| `dify_backup_action` | `none` | `none`, `backup`, or `restore` |
| `dify_backup_dir` | `{{ dify_deploy_dir }}/backups` | Backup directory |
| `dify_backup_file` | `""` | Restore file path (for restore) |
| `dify_backup_volume_file` | `""` | Volume tarball path (for restore) |
| `dify_backup_include_volumes` | `true` | Include volume data in backup |
| `dify_backup_format` | `custom` | `custom` (-Fc, pg_restore) or `plain` (-Fp, psql) |
| `dify_backup_compression` | `6` | Compression level 0-9 (custom format only) |
| `dify_backup_retention_days` | `7` | Days to retain backups before pruning |

## Dependencies

No role dependencies.

## Example Playbook

### Docker Compose (default, weaviate)

```yaml
- name: Deploy Dify
  hosts: workstations
  become: false
  vars:
    dify_deploy_dir: "{{ user.home }}/LLMOS/dify"
  roles:
    - role: b08x.llmops.dify
      tags: ["dify", "llmops"]
```

### Docker Compose with pgvector

```yaml
- name: Deploy Dify (pgvector) on ninjabot
  hosts: ninjabot
  become: false
  gather_facts: true
  vars:
    dify_container_runtime: docker
    dify_deploy_dir: "/mnt/local_storage/LLMOS/dify"
    dify_bind_localhost: false
    dify_vector_store: pgvector
    dify_db_username: postgres
    dify_db_password: "{{ vault_dify_db_password | default('difyai123456') }}"
    dify_db_database: dify
    dify_pgvector_user: postgres
    dify_pgvector_password: "{{ vault_dify_pgvector_password | default('difyai123456') }}"
    dify_pgvector_database: dify
  roles:
    - role: b08x.llmops.dify
      tags: ["dify", "llmops"]
```

### Podman

```yaml
- name: Deploy Dify (Podman) on tinybot
  hosts: tinybot
  become: false
  gather_facts: true
  vars:
    dify_container_runtime: podman
    dify_deploy_dir: "{{ user.home }}/LLMOS/dify"
    dify_bind_localhost: false
  roles:
    - role: b08x.llmops.dify
      tags: ["dify", "llmops"]
```

### Production with HTTPS

```yaml
- name: Deploy Dify (production, HTTPS)
  hosts: dify-prod
  become: false
  gather_facts: true
  vars:
    dify_deploy_dir: "/opt/dify"
    dify_bind_localhost: false
    dify_nginx_https_enabled: true
    dify_nginx_server_name: "dify.example.com"
    dify_init_password: "{{ vault_dify_init_password }}"
    dify_db_password: "{{ vault_dify_db_password }}"
    dify_redis_password: "{{ vault_dify_redis_password }}"
    dify_log_level: WARNING
  roles:
    - role: b08x.llmops.dify
      tags: ["dify", "llmops"]
```

## Backup and Restore

The role includes built-in backup and restore for both the PostgreSQL database
and the volume data (app storage, vector store, plugin daemon, sandbox, certs,
configs). Operations run via `pg_dump`/`pg_restore` inside the postgres
container — no host-side postgresql-client required.

### Backing up Dify

Set `dify_backup_action: backup` and run the playbook. The role will:

1. Dump the PostgreSQL database in the selected format (`custom` or `plain`)
2. Tar all volume directories and config files into a compressed archive
3. Prune backups older than `dify_backup_retention_days`

```bash
ansible-playbook dify-docker-ninjabot.yml \
  -e dify_backup_action=backup
```

Backups are written to `dify_backup_dir` (default:
`{{ dify_deploy_dir }}/backups`). Two files are produced:

| File | Description |
| --- | --- |
| `dify_YYYYMMDDThhmmss.dump` | PostgreSQL dump (custom format, `pg_restore` compatible) |
| `dify_volumes_YYYYMMDDThhmmss.tar.gz` | Volume data and config tarball |

### Restoring Dify

Set `dify_backup_action: restore` and point the role at your backup files.
The role will:

1. Stop the compose stack (if restoring volumes)
2. Extract the volume tarball
3. Start the compose stack and wait for PostgreSQL to be healthy
4. Restore the database from the dump file (format auto-detected by extension)

```bash
ansible-playbook dify-docker-ninjabot.yml \
  -e dify_backup_action=restore \
  -e dify_backup_file=/mnt/local_storage/LLMOS/dify/backups/dify_20250101T120000.dump \
  -e dify_backup_volume_file=/mnt/local_storage/LLMOS/dify/backups/dify_volumes_20250101T120000.tar.gz
```

To restore only the database, omit `dify_backup_volume_file` (or set
`dify_backup_include_volumes: false`):

```bash
ansible-playbook dify-docker-ninjabot.yml \
  -e dify_backup_action=restore \
  -e dify_backup_file=/mnt/local_storage/LLMOS/dify/backups/dify_20250101T120000.dump
```

To restore only volumes, omit `dify_backup_file`:

```bash
ansible-playbook dify-docker-ninjabot.yml \
  -e dify_backup_action=restore \
  -e dify_backup_include_volumes=true \
  -e dify_backup_volume_file=/mnt/local_storage/LLMOS/dify/backups/dify_volumes_20250101T120000.tar.gz
```

### Volume paths included in backup tarball

| Path | Contents |
| --- | --- |
| `volumes/app/storage` | Dify application data (user uploads, files) |
| `volumes/redis/data` | Redis persistence |
| `volumes/weaviate` | Weaviate vector store data |
| `volumes/pgvector/data` | pgvector data |
| `volumes/plugin_daemon` | Plugin storage |
| `volumes/sandbox/dependencies` | Code execution dependencies |
| `volumes/sandbox/conf` | Sandbox config |
| `volumes/certbot/conf` | Let's Encrypt certificates |
| `volumes/certbot/www` | ACME challenge files |
| `ssrf_proxy/` | SSRF proxy configs |
| `nginx/` | Reverse proxy configs |
| `docker-compose.yml` | Compose file |
| `.env` | Environment variables |

## Updating Dify

The role is idempotent — re-running the playbook converges the stack to the
current variable state. To update Dify to a new version:

1. **Back up first:**

   ```bash
   ansible-playbook dify-docker-ninjabot.yml \
     -e dify_backup_action=backup
   ```

2. **Bump the image tag** in your host or group vars:

   ```yaml
   # host_vars/ninjabot.yml
   dify_image_tag: "1.18.0"
   ```

   Or pass it as an extra var for a one-off update:

   ```bash
   ansible-playbook dify-docker-ninjabot.yml \
     -e dify_image_tag=1.18.0
   ```

3. **Force container recreation** so the new image is pulled and applied:

   ```bash
   ansible-playbook dify-docker-ninjabot.yml \
     -e dify_image_tag=1.18.0 \
     -e dify_force_recreate=true
   ```

   For Docker, the handler uses `docker_compose_v2` with `recreate: always`.
   For Podman, `--force-recreate` is passed to `podman compose up`.

4. **Verify** the stack is healthy:

   ```bash
   docker compose -f /mnt/local_storage/LLMOS/dify/docker-compose.yml ps
   curl -sf http://localhost/health
   ```

If something goes wrong, roll back by reverting `dify_image_tag` to the
previous version and re-running. To fully tear down:

```bash
docker compose -f /mnt/local_storage/LLMOS/dify/docker-compose.yml down
# or
podman compose -f /mnt/local_storage/LLMOS/dify/docker-compose.yml down
```

## Architecture

```
dify role
  tasks/main.yml
    debug entry → verify runtime → create dirs → render .env
    include docker.yml  (when runtime == docker)
      render docker-compose.yml.j2 → docker compose pull → docker_compose_v2
    include podman.yml   (when runtime == podman)
      render docker-compose.yml.j2 → podman compose down → pull → up -d
    firewalld (when bind_localhost == false)
    include backup.yml   (when backup_action != none)
  handlers/main.yml
    Restart Dify stack (docker_compose_v2 recreate, docker-only)
```

Services deployed:

| Service | Description | Port |
| --- | --- | --- |
| `nginx` | Reverse proxy entry point | 80, 443 |
| `api` | Dify API server | 5001 (internal) |
| `api_websocket` | WebSocket for collaboration (profile-gated) | 5001 (internal) |
| `worker` | Celery background worker | — |
| `worker_beat` | Celery beat scheduler | — |
| `web` | Next.js frontend | — |
| `db_postgres` | PostgreSQL 15 | 5432 (internal) |
| `redis` | Redis 6 cache/queue | 6379 (internal) |
| `sandbox` | Code execution sandbox | 8194 (internal) |
| `plugin_daemon` | Plugin management daemon | 5002, 5003 |
| `agent_backend` | Agent runtime backend | 5050 (internal) |
| `local_sandbox` | Agent shell workspaces | 5004 (internal) |
| `ssrf_proxy` | Squid SSRF proxy for sandbox | 3128 (internal) |
| `agent_ssrf_proxy` | Squid SSRF proxy for agent sandbox | 3128 (internal) |
| `weaviate` | Vector store (default, profile: `weaviate`) | 8080 (internal) |
| `pgvector` | Vector store (profile: `pgvector`) | 5432 (internal) |

### Networks

| Network | Driver | Purpose |
| --- | --- | --- |
| `ssrf_proxy_network` | bridge (internal) | API, worker, sandbox ↔ SSRF proxy |
| `local_sandbox_proxy_network` | bridge (internal) | Agent sandbox ↔ agent SSRF proxy |
| `agent_sandbox_network` | bridge (internal) | Agent backend ↔ local sandbox |

## Role Idempotency

True — the role is idempotent. Docker Compose `state: present` and
`podman compose up -d` are no-ops when containers are already running
with the current configuration.

## Role Atomicity

True — the role deploys the complete Dify stack in a single pass.

## Roll-back capabilities

Set `dify_force_recreate: false` (default) and revert the variable
changes. The compose stack will converge to the previous state on next
run. For full teardown, run `docker compose down` or `podman compose down`
in the deploy directory.

## License

GPL-2.0-or-later

## Author Information

b08x
