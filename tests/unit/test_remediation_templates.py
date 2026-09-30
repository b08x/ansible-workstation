"""Tier-1 template registry: known signatures resolve deterministically.

The langfuse template text is validated against the same guard the CLI runs,
and against the observed spellings of the live incident signatures.
"""

from __future__ import absolute_import, division, print_function

import pytest
import yaml
from remediation_guard import scan_playbook
from remediation_templates import (
    LANGFUSE_POD_EXITED_PLAYBOOK,
    TEMPLATE_VERSION,
    match_template,
)

# Every spelling the diagnose model produced for the live langfuse incident.
OBSERVED_POD_EXIT_SIGNATURES = (
    "podman:pod_state_exited",
    "podman:pod_exited",
    "podman:pod_exited+containers_exited",
    "podman:pod_exited_all_containers_exited",
)


@pytest.mark.parametrize("signature", OBSERVED_POD_EXIT_SIGNATURES)
def test_live_pod_exit_signatures_match(signature):
    template = match_template(error_signature=signature, service="langfuse", role="langfuse")
    assert template is not None
    assert template["template_id"] == "langfuse_pod_exited"
    assert template["template_version"] == TEMPLATE_VERSION


def test_container_level_signature_falls_through():
    """The original shm EINVAL class is a container problem, not a pod exit."""
    assert (
        match_template(
            error_signature="podman:container_state_improper+shm_mount_einval",
            service="langfuse",
            role="langfuse",
        )
        is None
    )


def test_pod_exit_on_other_service_falls_through():
    assert (
        match_template(error_signature="podman:pod_state_exited", service="nginx", role="unknown")
        is None
    )


def test_empty_signature_falls_through():
    assert match_template(error_signature="", service="langfuse", role="langfuse") is None


def test_template_playbook_shape():
    (play,) = yaml.safe_load(LANGFUSE_POD_EXITED_PLAYBOOK)
    assert list(play) == [
        "name",
        "hosts",
        "become",
        "gather_facts",
        "vars",
        "pre_tasks",
        "roles",
    ]
    assert play["roles"] == [{"role": "langfuse"}]
    assert play["vars"]["langfuse_force_recreate"] is True
    assert play["vars"]["langfuse_container_runtime"] == "podman"
    assert play["vars"]["langfuse_backup_action"] == "none"
    # The image-refresh pre-task must pull exactly the images the role uses.
    assert len(play["vars"]["langfuse_stack_images"]) == 6
    (pre_task,) = play["pre_tasks"]
    assert pre_task["name"].startswith("Re-pull")
    assert pre_task["ansible.builtin.command"]["cmd"] == "podman pull {{ item }}"
    assert pre_task["changed_when"] is True


def test_template_playbook_passes_volume_guard():
    assert scan_playbook(LANGFUSE_POD_EXITED_PLAYBOOK) == []


def test_template_carries_health_check_and_rationale():
    template = match_template(
        error_signature="podman:pod_state_exited", service="langfuse", role="langfuse"
    )
    assert template["health_check"]["kind"] == "http"
    assert template["health_check"]["target"].endswith("/api/public/health")
    assert "langfuse_force_recreate" in template["rationale"]
