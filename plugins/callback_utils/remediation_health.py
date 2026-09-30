# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Deterministic health assessment of gathered diagnostics.

Standard library only; the diagnose action plugin imports it. ``assess``
decides from container and pod state -- never from a model -- whether there is
anything to remediate, so a healthy host ends the run before any LLM call.

``split_history`` separates journal entries older than the most recent
container start, so evidence of an already-fixed failure is labelled as
history instead of being presented to the model as a live fault.

Limitation: without a list of expected services, a host where one container of
several has disappeared still looks healthy. A host with no containers at all
does not.
"""

from __future__ import absolute_import, division, print_function

import re
from datetime import datetime, timezone

__metaclass__ = type

FRACTION_RE = re.compile(r"(\.\d{6})\d+")


def assess(diagnostics):
    """Return a health verdict with the evidence behind it."""
    reasons = []
    containers_section = diagnostics.get("containers") or {}
    containers = []
    if not containers_section.get("ok"):
        reasons.append(
            "cannot read the container list: "
            f"{containers_section.get('error') or 'not collected'}"
        )
    else:
        containers = (containers_section.get("data") or {}).get("list") or []

    down = [_name(c) for c in containers if str(c.get("State", "")).lower() != "running"]
    unhealthy = [
        _name(c) for c in containers if "unhealthy" in str(c.get("Status", "")).lower()
    ]
    pods = ((diagnostics.get("pods") or {}).get("data") or {}).get("list") or []
    pods_down = [
        str(p.get("Name") or p.get("name"))
        for p in pods
        if str(p.get("Status") or p.get("status") or "") != "Running"
    ]

    if containers_section.get("ok") and not containers:
        reasons.append("no containers found; expected services may be missing")
    if down:
        reasons.append(f"not running: {', '.join(down)}")
    if unhealthy:
        reasons.append(f"health check failing: {', '.join(unhealthy)}")
    if pods_down:
        reasons.append(f"pods not running: {', '.join(pods_down)}")

    running = len(containers) - len(down)
    healthy = not reasons
    if healthy:
        pod_text = f", {len(pods)} pods running" if pods else ""
        summary = (
            f"healthy: {running} of {len(containers)} containers running{pod_text}; "
            "nothing to remediate"
        )
    else:
        summary = "; ".join(reasons)
    return {
        "healthy": healthy,
        "summary": summary,
        "containers": len(containers),
        "running": running,
        "down": down,
        "unhealthy": unhealthy,
        "pods_down": pods_down,
        "reasons": reasons,
        "warnings": _host_warnings(diagnostics),
    }


def split_history(diagnostics):
    """Move journal entries older than the latest container start to *_history."""
    boundary = _latest_start(diagnostics)
    journal = diagnostics.get("journal") or {}
    data = journal.get("data")
    if boundary is None or not isinstance(data, dict):
        return diagnostics
    cutoff = boundary.timestamp() * 1e6
    split = {}
    for scope, entries in data.items():
        if not isinstance(entries, list):
            split[scope] = entries
            continue
        current, history = [], []
        for entry in entries:
            stamp = _to_float(entry.get("__REALTIME_TIMESTAMP"))
            (history if stamp is not None and stamp < cutoff else current).append(entry)
        split[scope] = current
        if history:
            split[f"{scope}_history"] = history
    result = dict(diagnostics)
    result["journal"] = dict(
        journal,
        data=split,
        history_before=boundary.astimezone(timezone.utc).isoformat(),
    )
    return result


def _host_warnings(diagnostics):
    security = (diagnostics.get("host_security") or {}).get("data") or {}
    warnings = []
    mode = str(security.get("selinux_mode") or "")
    config = str(security.get("selinux_config") or "")
    cmdline = str(security.get("kernel_cmdline") or "")
    if "selinux=0" in cmdline.split():
        warnings.append(
            "SELinux is disabled by the selinux=0 boot argument"
            + (f" although /etc/selinux/config says {config}" if config else "")
        )
    elif mode.lower() == "disabled" and config and config.lower() != "disabled":
        warnings.append(f"SELinux is disabled although /etc/selinux/config says {config}")
    return warnings


def _latest_start(diagnostics):
    inspects = (
        ((diagnostics.get("containers") or {}).get("data") or {}).get("inspect") or {}
    )
    latest = None
    for entry in inspects.values():
        records = (entry or {}).get("data") if isinstance(entry, dict) else None
        if isinstance(records, dict):
            records = [records]
        for record in records or []:
            started = _parse_time((record.get("State") or {}).get("StartedAt"))
            if started is not None and (latest is None or started > latest):
                latest = started
    return latest


def _parse_time(value):
    if not value:
        return None
    text = FRACTION_RE.sub(r"\1", str(value)).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # podman reports never-started containers as year 1.
    return parsed if parsed.year >= 2000 else None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(container):
    names = container.get("Names") or container.get("Name") or container.get("Id") or "?"
    if isinstance(names, list):
        names = names[0] if names else "?"
    return str(names)
