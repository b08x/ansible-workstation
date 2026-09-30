# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Deterministic remediation templates for known error signatures.

Tier 1 of the two-tier generation design: when a diagnosis lands on an error
signature this registry knows, the remediation playbook is a hand-authored
template, not model output. A template is a known-good invocation of the role
that manages the service, so no language model is consulted for generation and
the guard chain (volume scan, syntax-check, ansible-lint) still runs over the
template text exactly as it does over model output.

Unknown signatures fall back to tier 2, the LLM path in
``remediation_signatures.GenerateRemediation``; callers decide by checking
the return value of :func:`match_template`.

Every template carries ``template_version`` so rows indexed under one revision
of a template are distinguishable from rows indexed under another.
"""

from __future__ import absolute_import, division, print_function

import re

__metaclass__ = type

TEMPLATE_VERSION = "1.1.0"


def _tokens(error_signature: str) -> list[str]:
    """Split a normalized error signature into comparison tokens."""
    return [t for t in re.split(r"[_+:.\s]", (error_signature or "").lower()) if t]


# Mirrors playbooks/langfuse-podman.yml with langfuse_force_recreate: true,
# plus a pre-task that re-pulls the stack images. Keep the var set in sync
# with the deploy playbook and the image list in sync with
# roles/langfuse/vars/main.yml: the template must reproduce the deployed
# configuration, changing only the force-recreate knob and the image refresh.
LANGFUSE_POD_EXITED_PLAYBOOK = """\
---
- name: Refresh the langfuse stack images and recreate the exited pod
  hosts: all
  become: false
  gather_facts: true
  vars:
    # Container runtime
    langfuse_container_runtime: podman

    # Deployment
    langfuse_deploy_dir: "{{ user.home }}/LLMOS/langfuse"
    langfuse_project_name: langfuse

    # Force pod and container recreation: this is the remediation. The role
    # removes the pod and containers; the named volumes are untouched.
    langfuse_force_recreate: true

    # Bind
    langfuse_bind_localhost: false

    # Ports
    langfuse_web_port: 3000
    langfuse_worker_port: 3030
    langfuse_minio_api_port: 9090
    langfuse_minio_console_port: 9091

    # URLs
    langfuse_nextauth_url: "http://tinybot:3000"
    langfuse_nextauth_secret: "mysecret"
    langfuse_salt: "mysalt"
    langfuse_encryption_key: "0000000000000000000000000000000000000000000000000000000000000000"

    # PostgreSQL
    langfuse_postgres_user: postgres
    langfuse_postgres_password: "{{ vault_langfuse_postgres_password | default('postgres') }}"
    langfuse_postgres_db: postgres

    # ClickHouse
    langfuse_clickhouse_user: clickhouse
    langfuse_clickhouse_password: "{{ vault_langfuse_clickhouse_password | default('clickhouse') }}"

    # Redis
    langfuse_redis_auth: "{{ vault_langfuse_redis_auth | default('myredissecret') }}"

    # MinIO
    langfuse_minio_root_user: minio
    langfuse_minio_root_password: "{{ vault_langfuse_minio_root_password | default('miniosecret') }}"

    # S3 buckets
    langfuse_s3_event_upload_bucket: langfuse
    langfuse_s3_media_upload_bucket: langfuse
    langfuse_s3_batch_export_bucket: langfuse

    # Feature flags
    langfuse_telemetry_enabled: true
    langfuse_enable_experimental_features: false

    # ClickHouse cluster
    langfuse_clickhouse_cluster_enabled: false
    langfuse_clickhouse_cluster_name: default

    # Backup
    langfuse_backup_action: "none"
    langfuse_backup_dir: "{{ user.home }}/LLMOS/langfuse/backups"

    # Image tags
    langfuse_image_tag: "latest"
    langfuse_clickhouse_image_tag: "25.12"
    langfuse_postgres_version: "17"

    # Stack images to re-pull before the role recreates the containers.
    # Values mirror roles/langfuse/vars/main.yml.
    langfuse_stack_images:
      - "docker.io/library/postgres:{{ langfuse_postgres_version }}"
      - "docker.io/clickhouse/clickhouse-server:{{ langfuse_clickhouse_image_tag }}"
      - "docker.io/library/redis:7"
      - "cgr.dev/chainguard/minio"
      - "docker.langfuse.com/langfuse/langfuse:{{ langfuse_image_tag }}"
      - "docker.langfuse.com/langfuse/langfuse-worker:{{ langfuse_image_tag }}"
  pre_tasks:
    - name: Re-pull the stack images to replace damaged local layers
      ansible.builtin.command:
        cmd: "podman pull {{ item }}"
      loop: "{{ langfuse_stack_images }}"
      changed_when: true
  roles:
    - role: langfuse
"""


def _is_langfuse_pod_exit(error_signature: str, service: str, role: str) -> bool:
    """'langfuse pod exited' in any of the spellings the diagnose model uses.

    The signature is normalized but not standardized across runs, so matching
    is token-based: ``podman:pod_state_exited``,
    ``podman:pod_exited+containers_exited`` and
    ``podman:pod_exited_all_containers_exited`` all match. The ``pod`` token
    must stand alone so a container-level signature like
    ``podman:container_state_improper+shm_mount_einval`` does not.
    """
    if "langfuse" not in f"{service} {role}".lower():
        return False
    tokens = _tokens(error_signature)
    return "pod" in tokens and any(t.startswith("exit") for t in tokens)


_TEMPLATES = (
    {
        "template_id": "langfuse_pod_exited",
        "matches": _is_langfuse_pod_exit,
        "playbook_yaml": LANGFUSE_POD_EXITED_PLAYBOOK,
        "rationale": (
            "The root cause on the live incident was damaged image layers in "
            "the local podman store: containers whose image lacks /etc/mtab "
            "failed to start with 'creating /etc/mtab symlink: operation not "
            "permitted'. Re-pulling the stack images replaces those layers; "
            "re-applying the langfuse role with langfuse_force_recreate: "
            "true then stops and removes the exited pod and its containers "
            "and recreates them from the fresh images, while the named "
            "volumes stay in place."
        ),
        "health_check": {
            "kind": "http",
            "target": "http://localhost:3000/api/public/health",
        },
    },
)


def match_template(*, error_signature: str, service: str, role: str):
    """Return the deterministic remediation for a known signature, or None.

    Callers run the returned playbook through the same guard chain as model
    output; a template is a shortcut for generation, never for validation.
    """
    for template in _TEMPLATES:
        if template["matches"](error_signature, service, role):
            return {
                "template_id": template["template_id"],
                "template_version": TEMPLATE_VERSION,
                "playbook_yaml": template["playbook_yaml"],
                "rationale": template["rationale"],
                "health_check": dict(template["health_check"]),
            }
    return None
