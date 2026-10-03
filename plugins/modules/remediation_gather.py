#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Read-only diagnostics gatherer for the LLM remediation pipeline.

Runs on the target host, collects podman/journald/mount/SELinux state, and
returns one JSON document. Every command here is read-only; the module reports
``changed=false`` and is safe in check mode. Values that look like secrets
are redacted across the whole document (inspect output, logs, journal) before
anything leaves the host.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: remediation_gather
short_description: Collect read-only diagnostics for LLM-driven remediation
description:
  - Runs read-only commands on the target host (podman, journalctl, findmnt,
    ausearch) and reads /proc and /etc/os-release to build one JSON document
    describing the current state of podman pods, containers, logs, mounts and
    recent denials.
  - The module never modifies the host. It reports C(changed=false) and runs
    the same read-only commands in check mode.
  - Secret-looking values are replaced with the string C(REDACTED) in every
    section before the document is returned. This covers fields and C(NAME=value)
    entries whose names match pass/secret/key/token/salt/auth, including inside
    log and journal text, and the password part of any C(scheme://user:pass@)
    URL, such as C(DATABASE_URL).
options:
  pod:
    description:
      - Optional pod name. When set, only that pod, its containers and their
        logs are collected. Containers are matched by their C(Pod) field, or by
        a container name containing the pod name.
    type: str
    required: false
  log_lines:
    description:
      - Number of log lines to tail per container.
    type: int
    default: 200
  journal_units:
    description:
      - systemd unit globs passed to journalctl via C(-u), collected from both
        the user journal and the system journal.
    type: list
    elements: str
    default: ["podman*", "conmon*", "user@*"]
  since:
    description:
      - Time window passed to journalctl C(--since) and ausearch C(-ts).
    type: str
    default: -1h
author:
  - b08x
"""

EXAMPLES = r"""
- name: Gather diagnostics for the langfuse pod
  remediation_gather:
    pod: langfuse

- name: Gather everything from the last hour
  remediation_gather:
    since: -1h
"""

RETURN = r"""
diagnostics:
  description:
    - One JSON document with one key per section. Each section is an object
      C({ok, data, error}) so a single failing command cannot fail the gather.
  returned: always
  type: dict
  contains:
    host:
      description: OS release, kernel, podman version, disk and memory.
      type: dict
    pods:
      description: C(podman pod ps) and per-pod inspect output.
      type: dict
    containers:
      description: C(podman ps -a) and per-container inspect output, redacted.
      type: dict
    logs:
      description: Tailed container logs, keyed by container name.
      type: dict
    journal:
      description: User and system journal entries for the requested units.
      type: dict
    mounts:
      description: C(findmnt -J) filtered to shm, overlay and /run/user.
      type: dict
    selinux:
      description: Recent AVC denials from ausearch, or null with a reason.
      type: dict
    host_security:
      description:
        - Host-level causes that surface as container errors. SELinux mode
          (C(getenforce)) and configured mode, kernel command line, active
          LSMs, current-boot kernel log lines about mounts, tmpfs, overlay
          and SELinux, recent reboots (C(last -x)), and whether the user
          lingers (C(loginctl)). Missing tools are reported per field.
      type: dict
changed:
  description: Always false. The gather is read-only.
  type: bool
"""

import getpass
import json
import re
import socket

from ansible.module_utils.basic import AnsibleModule

SECRET_KEY_RE = re.compile(r"(?i)pass|secret|key|token|salt|auth")
REDACTED = "REDACTED"
# scheme://user:password@host -- the password is kept out of every string,
# whatever key it sits under (DATABASE_URL carries the Postgres password).
URL_CREDENTIAL_RE = re.compile(r"([a-z][a-z0-9+.-]*://[^/\s:@]*):[^/\s@]+@", re.IGNORECASE)
# NAME=value inside free text (logs, journal messages) with a secret-looking NAME.
TEXT_ASSIGNMENT_RE = re.compile(
    r"\b([A-Za-z0-9_.-]*(?:pass|secret|key|token|salt|auth)[A-Za-z0-9_.-]*)=([^\s\"',;]+)",
    re.IGNORECASE,
)


def _run(module, args):
    """Run one read-only command, returning an {ok, data, error} envelope."""
    try:
        rc, out, err = module.run_command(args)
    except (OSError, ValueError) as e:
        return {"ok": False, "data": None, "error": f"failed to run {args[0]}: {e}"}
    if rc != 0:
        return {"ok": False, "data": None, "error": err.strip() or f"{args[0]} exited {rc}"}
    return {"ok": True, "data": out, "error": None}


def _run_json(module, args):
    envelope = _run(module, args)
    if not envelope["ok"]:
        return envelope
    try:
        envelope["data"] = json.loads(envelope["data"])
    except ValueError as e:
        envelope["ok"] = False
        envelope["error"] = f"{args[0]} produced non-JSON output: {e}"
    return envelope


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return {"ok": True, "data": fh.read(), "error": None}
    except OSError as e:
        return {"ok": False, "data": None, "error": f"{path}: {e}"}


def redact(value):
    """Strip secret-looking values so nothing sensitive leaves the host."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(item, str) and SECRET_KEY_RE.search(key):
                out[key] = REDACTED
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str) and "=" in item:
                name, _, val = item.partition("=")
                if SECRET_KEY_RE.search(name):
                    item = f"{name}={REDACTED}"
            out.append(redact(item))
        return out
    if isinstance(value, str):
        value = URL_CREDENTIAL_RE.sub(rf"\1:{REDACTED}@", value)
        return TEXT_ASSIGNMENT_RE.sub(rf"\1={REDACTED}", value)
    return value


KERNEL_LOG_RE = re.compile(
    r"(?i)overlay|tmpfs|shm|selinux|avc|context|mount|einval|eperm|denied|not permitted"
)


def gather_host_security(module):
    """Host-level state behind container mount failures (EINVAL, EPERM)."""
    data = {}
    errors = []

    mode = _run(module, ["getenforce"])
    if mode["ok"]:
        data["selinux_mode"] = mode["data"].strip()
    else:
        errors.append(f"getenforce: {mode['error']}")

    config = _read_file("/etc/selinux/config")
    if config["ok"]:
        for line in config["data"].splitlines():
            if line.startswith("SELINUX="):
                data["selinux_config"] = line.partition("=")[2].strip()
    else:
        data["selinux_config_error"] = config["error"]

    for field, path in (("kernel_cmdline", "/proc/cmdline"), ("lsm", "/sys/kernel/security/lsm")):
        read = _read_file(path)
        if read["ok"]:
            value = read["data"].strip()
            data[field] = value.split(",") if field == "lsm" else value
        else:
            data[f"{field}_error"] = read["error"]

    kernel = _run(module, ["journalctl", "-k", "-b", "--no-pager", "-o", "short-iso"])
    if kernel["ok"]:
        lines = [ln for ln in kernel["data"].splitlines() if KERNEL_LOG_RE.search(ln)]
        data["kernel_log"] = lines[-50:]
    else:
        errors.append(f"journalctl -k: {kernel['error']}")

    boots = _run(module, ["last", "-x", "-n", "6", "reboot", "shutdown"])
    if boots["ok"]:
        data["boots"] = [ln for ln in boots["data"].splitlines() if ln.strip()][:6]
    else:
        errors.append(f"last: {boots['error']}")

    linger = _run(module, ["loginctl", "show-user", getpass.getuser(), "-p", "Linger", "--value"])
    if linger["ok"]:
        data["linger"] = linger["data"].strip()
    else:
        errors.append(f"loginctl: {linger['error']}")

    return {"ok": True, "data": data, "error": "; ".join(errors) or None}


def gather_host(module):
    data = {}
    os_release = _read_file("/etc/os-release")
    if os_release["ok"]:
        fields = {}
        for line in os_release["data"].splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                fields[key] = val.strip('"')
        data["os_release"] = fields
    else:
        data["os_release_error"] = os_release["error"]

    meminfo = _read_file("/proc/meminfo")
    if meminfo["ok"]:
        fields = {}
        for line in meminfo["data"].splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()
        data["meminfo"] = fields
    else:
        data["meminfo_error"] = meminfo["error"]

    for name, args in (
        ("kernel", ["uname", "-r"]),
        ("podman_version", ["podman", "version", "--format", "json"]),
        ("disk", ["df", "-h"]),
    ):
        result = _run_json(module, args) if name == "podman_version" else _run(module, args)
        if result["ok"]:
            data[name] = result["data"]
        else:
            data[f"{name}_error"] = result["error"]

    data["hostname"] = socket.gethostname()
    return {"ok": True, "data": data, "error": None}


def _container_pod_name(container, pod_name):
    """Pod a container belongs to, tolerating older podman ps JSON shapes."""
    pod = container.get("Pod") or container.get("pod")
    if isinstance(pod, dict):
        pod = pod.get("Names") or pod.get("Id") or pod.get("Name")
    return pod or ""


def _select_containers(containers, pod):
    """Containers to inspect: pod members, name matches, or all."""
    if not pod:
        return containers
    selected = []
    for container in containers:
        names = container.get("Names") or [container.get("Name") or ""]
        if isinstance(names, str):
            names = [names]
        if _container_pod_name(container, pod) == pod or any(pod in n for n in names):
            selected.append(container)
    return selected


def gather_pods(module, pod):
    ps = _run_json(module, ["podman", "pod", "ps", "--format", "json"])
    if not ps["ok"]:
        return ps
    pods = ps["data"] or []
    if pod:
        pods = [p for p in pods if (p.get("Name") or p.get("name")) == pod]
    inspects = {}
    for p in pods:
        name = p.get("Name") or p.get("name")
        inspects[name] = _run_json(module, ["podman", "pod", "inspect", name])
    return {"ok": True, "data": {"list": pods, "inspect": inspects}, "error": None}


def gather_containers(module, pod):
    ps = _run_json(module, ["podman", "ps", "-a", "--format", "json"])
    if not ps["ok"]:
        return ps
    containers = ps["data"] or []
    selected = _select_containers(containers, pod)
    inspects = {}
    for container in selected:
        name = container.get("Names")
        if isinstance(name, list):
            name = name[0] if name else container.get("Id")
        result = _run_json(module, ["podman", "inspect", container.get("Id") or name])
        if result["ok"]:
            result["data"] = redact(result["data"])
        inspects[name] = result
    return {
        "ok": True,
        "data": {"list": selected, "inspect": inspects},
        "error": None,
    }


def gather_logs(module, containers_data, log_lines):
    logs = {}
    error = None
    for container in containers_data.get("list") or []:
        names = container.get("Names") or [container.get("Name") or ""]
        if isinstance(names, str):
            names = [names]
        if not names or not names[0]:
            continue
        result = _run(module, ["podman", "logs", "--tail", str(log_lines), names[0]])
        logs[names[0]] = result
        if not result["ok"]:
            error = result["error"]
    return {"ok": True, "data": logs, "error": error}


def gather_journal(module, units, since):
    unit_args = []
    for unit in units:
        unit_args.extend(["-u", unit])
    data = {}
    errors = []
    for scope, extra in (("user", ["--user"]), ("system", [])):
        result = _run(
            module,
            ["journalctl", *extra, *unit_args, "--since", since, "-o", "json", "--no-pager"],
        )
        data[scope] = None if not result["ok"] else _json_entries(result["data"])
        if not result["ok"]:
            errors.append(f"{scope}: {result['error']}")
    return {"ok": True, "data": data, "error": "; ".join(errors) or None}


def _json_entries(text):
    """journalctl -o json emits one JSON object per line, not an array."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def gather_mounts(module):
    result = _run_json(module, ["findmnt", "-J"])
    if not result["ok"]:
        return result
    selected = []

    def walk(node):
        for fs in node or []:
            target = fs.get("target", "")
            fstype = fs.get("fstype", "")
            source = fs.get("source", "")
            if "shm" in target or "shm" in source:
                selected.append(fs)
            elif "overlay" in fstype:
                selected.append(fs)
            elif target.startswith("/run/user"):
                selected.append(fs)
            walk(fs.get("children"))

    walk(result["data"].get("filesystems"))
    return {"ok": True, "data": selected, "error": None}


def gather_selinux(module, since):
    """ausearch needs root; a permission failure is a normal degraded result."""
    result = _run(module, ["ausearch", "-m", "AVC", "-ts", "recent"])
    if result["ok"]:
        return result
    return {"ok": False, "data": None, "error": f"ausearch unavailable: {result['error']}"}


def main():
    module = AnsibleModule(
        argument_spec={
            "pod": {"type": "str", "required": False, "default": None},
            "log_lines": {"type": "int", "default": 200},
            "journal_units": {
                "type": "list",
                "elements": "str",
                "default": ["podman*", "conmon*", "user@*"],
            },
            "since": {"type": "str", "default": "-1h"},
        },
        supports_check_mode=True,
    )

    pod = module.params["pod"]
    log_lines = module.params["log_lines"]
    journal_units = module.params["journal_units"]
    since = module.params["since"]

    host = gather_host(module)
    pods = gather_pods(module, pod)
    containers = gather_containers(module, pod)
    logs = gather_logs(module, containers["data"], log_lines)
    journal = gather_journal(module, journal_units, since)
    mounts = gather_mounts(module)
    selinux = gather_selinux(module, since)
    host_security = gather_host_security(module)

    diagnostics = {
        "host": host,
        "pods": pods,
        "containers": containers,
        "logs": logs,
        "journal": journal,
        "mounts": mounts,
        "selinux": selinux,
        "host_security": host_security,
    }
    # One pass over the whole document: logs and journal carry secrets too.
    module.exit_json(changed=False, diagnostics=redact(diagnostics))


if __name__ == "__main__":
    main()
