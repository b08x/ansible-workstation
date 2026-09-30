# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""DSPy signatures for the LLM diagnose-and-remediate pipeline.

Follows the ``llm_signatures.py`` pattern: ``dspy`` is imported only inside
:meth:`build`, and ``SIGNATURE_VERSION`` is recorded with every prediction so
rows produced by different revisions of these prompts do not pool together.

The language model's role ends at producing text. ``GenerateRemediation``
emits playbook YAML as a string; nothing here executes anything, and the
orchestrating playbook runs the result only after human approval.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

SIGNATURE_VERSION = "1.2.0"

# Tier-2 generation is seeded with this skeleton: a hand-authored, lint-clean
# shape the model fills in. Known incident classes never reach it; they are
# served by the deterministic templates in remediation_templates.py.
PLAYBOOK_SKELETON = """\
---
- name: <one imperative sentence naming the remediation>
  hosts: all
  become: false
  gather_facts: false
  tasks:
    - name: <one imperative sentence naming the task>
      <module FQCN>:
        <module parameters, one per line>
      # changed_when: only on command/shell tasks
"""

# Hints used when trimming diagnostics down to the context budget.
ERROR_HINTS = (
    "error",
    "fail",
    "invalid",
    "denied",
    "improper",
    "einval",
    "fatal",
    "critical",
    "exit",
    "unhealthy",
)

SEVERITY_VALUES = ("low", "medium", "high", "critical")


def build():
    """Construct the DiagnoseIncident and GenerateRemediation signatures.

    Deferred into a function so importing this module does not import
    ``dspy``; callers that only need :func:`trim_diagnostics` stay cheap.
    """
    from typing import Literal

    import dspy
    from pydantic import BaseModel, Field

    class HealthCheck(BaseModel):
        """Post-remediation check the orchestrating playbook can run."""

        kind: Literal["http", "podman"] = Field(
            description="http: fetch a URL and expect 200. podman: run "
            "'podman healthcheck run <target>'"
        )
        target: str = Field(description="URL for kind=http, container name for kind=podman")

    class DiagnoseIncident(dspy.Signature):
        """Diagnose a failing host from read-only diagnostics JSON.

        Report only what the diagnostics support. The error signature must be
        normalized and host-independent: lowercase, words joined with
        underscores or plus signs, no hostnames, IPs or timestamps, so the
        same failure class on any host yields the same string.

        Check host_security before blaming container settings. Container
        mount errors (EINVAL, EPERM, "operation not permitted", "invalid
        argument") often have a host-level cause there: SELinux disabled by
        a selinux=0 boot argument, kernel log lines such as "tmpfs: Unknown
        parameter 'context'", a recent reboot, or a user who does not linger.
        Journal keys ending in _history hold entries from before the most
        recent container start; they may describe problems already resolved,
        so weigh current container state above them.
        """

        diagnostics_json: str = dspy.InputField(
            desc="Read-only diagnostics from remediation_gather, as JSON"
        )

        summary: str = dspy.OutputField(
            desc="Two to four sentences: what is failing, since when, and the "
            "evidence from the diagnostics"
        )
        error_signature: str = dspy.OutputField(
            desc="Normalized, host-independent failure class, e.g. "
            "'podman:container_state_improper+shm_mount_einval'"
        )
        service: str = dspy.OutputField(desc="The affected service or workload")
        role: str = dspy.OutputField(
            desc="The name of the Ansible role directory in roles/ that "
            "manages this service (for example 'langfuse'), or 'unknown'"
        )
        severity: Literal["low", "medium", "high", "critical"] = dspy.OutputField(
            desc="low, medium, high or critical"
        )

    class GenerateRemediation(dspy.Signature):
        """Write an Ansible playbook that remediates the diagnosed incident.

        Format the playbook exactly like the skeleton: play keys in the
        order name, hosts, become, gather_facts, tasks; the tasks list
        indented four spaces; every play and every task named; playbook_yaml
        is raw YAML with no markdown code fences; YAML booleans spelled
        true or false, never yes/no/on/off. Rules the playbook must obey:
        hosts is 'all' (the orchestrating run applies -l); every module uses
        its FQCN; never remove podman volumes, never delete volume data,
        never pass -v to podman rm / podman pod rm -- keep persistent data
        intact. Valid podman modules are containers.podman.podman_pod
        (state: started/stopped/created) and containers.podman.podman_container;
        there is no containers.podman.pod module. For anything without a
        module, use ansible.builtin.command with changed_when. Do not use
        become for podman tasks: the pods run rootless under the user
        account. Write become: true, not 'yes', and give become_user a user
        name, not a UID.

        Never leave the service down if the fix fails. Before any task that
        removes or recreates a container or pod (state: absent, recreate:
        true, podman rm, podman pod rm, compose down), an earlier task must
        test-run the replacement image: ansible.builtin.command: podman run
        --rm <image> <a short command such as --version or true>, with
        changed_when: false. Replace a container in this order: test-run the
        image; podman stop <name>; podman rename <name> <name>-old; create
        and start the new container; check that it answers; only then remove
        <name>-old. Copy every setting of the existing container from the
        diagnostics (image, command, ports, volumes, environment, restart
        policy) and change only what the diagnosis requires. If the
        diagnosis points at a host-level cause, do not recreate containers
        at all: describe the host fix in the rationale and write a playbook
        that only reports it with ansible.builtin.debug.
        """

        summary: str = dspy.InputField(desc="The incident summary")
        diagnostics_json: str = dspy.InputField(desc="Trimmed read-only diagnostics, as JSON")
        similar_incidents: str = dspy.InputField(
            desc="Similar past incidents with their confirmed remediation "
            "playbooks, as JSON. May be an empty list."
        )
        role_context: str = dspy.InputField(
            desc="Where the role that manages this service lives, if known"
        )
        playbook_skeleton: str = dspy.InputField(
            desc="The exact play and task shape to fill in; the playbook "
            "must follow this skeleton's key order and indentation"
        )

        playbook_yaml: str = dspy.OutputField(
            desc="A complete Ansible playbook as YAML text, remedying the "
            "diagnosed failure without touching volumes"
        )
        rationale: str = dspy.OutputField(
            desc="Two to four sentences: why this remediation addresses the "
            "diagnosed failure class"
        )
        health_check: HealthCheck = dspy.OutputField(
            desc="One check proving the service is healthy again"
        )

    return DiagnoseIncident, GenerateRemediation


def trim_diagnostics(diagnostics: dict, char_budget: int = 24000) -> dict:
    """Trim gather output to a prompt-sized document, failures first.

    Priorities: host state, SELinux denials, mounts, then the pods and
    containers that are not running, then recent log and journal lines that
    mention an error. Sections are added in that order until the budget is
    spent; whatever does not fit is dropped, never silently truncated
    mid-section.
    """
    import json as _json

    sections = (
        ("host", _trim_host),
        ("host_security", _trim_host_security),
        ("selinux", _keep),
        ("mounts", _keep),
        ("pods", _trim_pods),
        ("containers", _trim_containers),
        ("logs", _trim_logs),
        ("journal", _trim_journal),
    )
    trimmed = {}
    used = 0
    for name, trimmer in sections:
        section = diagnostics.get(name)
        if section is None:
            trimmed[name] = {"ok": False, "data": None, "error": "not collected"}
            continue
        data = trimmer(section)
        encoded = _json.dumps(data, default=str)
        if used + len(encoded) > char_budget:
            trimmed[name] = {
                "ok": False,
                "data": None,
                "error": "omitted: context budget exceeded",
            }
            continue
        used += len(encoded)
        trimmed[name] = {"ok": True, "data": data, "error": None}
    return trimmed


def _keep(section):
    return section.get("data")


def _trim_host_security(section):
    data = dict(section.get("data") or {})
    if isinstance(data.get("kernel_log"), list):
        data["kernel_log"] = data["kernel_log"][-30:]
    if section.get("error"):
        data["collection_errors"] = section["error"]
    return data


def _trim_host(section):
    data = dict(section.get("data") or {})
    # meminfo is a large table; keep the headline numbers only.
    meminfo = data.get("meminfo")
    if isinstance(meminfo, dict):
        data["meminfo"] = {
            key: meminfo[key]
            for key in ("MemTotal", "MemFree", "MemAvailable", "SwapTotal", "SwapFree")
            if key in meminfo
        }
    disk = data.get("disk")
    if isinstance(disk, str):
        data["disk"] = disk.splitlines()[:6]
    return data


def _trim_pods(section):
    data = section.get("data") or {}
    pods = data.get("list") or []
    inspects = data.get("inspect") or {}
    failing = [p for p in pods if (p.get("Status") or p.get("status")) != "Running"]
    keep = failing or pods
    keep_names = {(p.get("Name") or p.get("name")) for p in keep}
    return {
        "list": keep,
        "inspect": {name: inspects.get(name) for name in keep_names if name in inspects},
    }


def _trim_containers(section):
    data = section.get("data") or {}
    containers = data.get("list") or []
    inspects = data.get("inspect") or {}

    def running(entry):
        state = str(entry.get("State") or entry.get("state") or "").lower()
        return state == "running"

    failing = [c for c in containers if not running(c)]
    keep = failing or containers
    keep_names = []
    for entry in keep:
        names = entry.get("Names") or [entry.get("Name")]
        if isinstance(names, str):
            names = [names]
        if names and names[0]:
            keep_names.append(names[0])
    return {
        "list": keep,
        "inspect": {name: inspects.get(name) for name in keep_names if name in inspects},
    }


def _trim_logs(section):
    data = section.get("data") or {}
    trimmed = {}
    for container, entry in data.items():
        text = (entry or {}).get("data") if isinstance(entry, dict) else entry
        if not isinstance(text, str):
            continue
        lines = [ln for ln in text.splitlines() if _is_error_line(ln)]
        if not lines:
            lines = text.splitlines()[-30:]
        trimmed[container] = lines[-30:]
    return trimmed


def _trim_journal(section):
    data = section.get("data") or {}
    trimmed = {}
    for scope, entries in (data or {}).items():
        if not isinstance(entries, list):
            continue
        selected = []
        for entry in entries:
            message = str(entry.get("MESSAGE", ""))
            priority = str(entry.get("PRIORITY", ""))
            if priority in ("2", "3") or _is_error_line(message):
                selected.append(
                    {
                        "__REALTIME_TIMESTAMP": entry.get("__REALTIME_TIMESTAMP"),
                        "PRIORITY": priority,
                        "_SYSTEMD_UNIT": entry.get("_SYSTEMD_UNIT"),
                        "MESSAGE": message[:500],
                    }
                )
        # journalctl emits oldest-first; the interesting entries are usually
        # the most recent ones.
        trimmed[scope] = selected[-40:]
    return trimmed


def _is_error_line(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in ERROR_HINTS)
