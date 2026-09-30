# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Safety guard for generated remediation playbooks.

A playbook that removes podman volumes or deletes volume data is rejected
before a human is ever offered the chance to approve it. Two passes run over
the playbook: a structural walk of the parsed YAML for module options that are
destructive by configuration, and a regex pass over every string in the
document for destructive shell commands, wherever they hide (``shell``,
``command``, ``argv`` lists, variables, templates).

Play/block/task ``vars`` and ``set_fact`` values are substituted into
``{{ name }}`` references before either pass. A deletion whose target still
contains an unresolved template (a loop item, a registered result) cannot be
proven safe and is rejected.

Conservative by design: a false positive costs one rejected generation, a
false negative costs the incident's data.

``scan_outage`` is the second guard. It rejects a playbook that removes or
recreates a container or pod before an earlier task has test-run the
replacement image (``podman run --rm <image> ...``). A draft that deletes a
working container and then fails to create the new one leaves the service
down; that is what happened to ollama on tinybot on 2026-09-30.
"""

from __future__ import absolute_import, division, print_function

import re
from typing import Any

__metaclass__ = type

VOLUME_DATA_MARKERS = (
    ".local/share/containers/storage/volumes",
    "/var/lib/containers/storage/volumes",
)
# Directories whose removal takes the volumes directory with it.
VOLUME_ANCESTOR_RE = re.compile(
    r"^(?:"
    r"(?:~|\$HOME|\$\{HOME\}|/home/[^/\s]+|/root)"
    r"(?:/\.local(?:/share(?:/containers(?:/storage)?)?)?)?"
    r"|/|/home|/var(?:/lib(?:/containers(?:/storage)?)?)?"
    r")$"
)
# Home-directory spellings that Ansible resolves at runtime.
HOME_TEMPLATE_RE = re.compile(
    r"\{\{\s*(?:ansible_env\.HOME|ansible_env\[['\"]HOME['\"]\]|ansible_user_dir"
    r"|lookup\(\s*['\"]env['\"]\s*,\s*['\"]HOME['\"]\s*\))\s*\}\}"
)
VAR_TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*(?:\|[^}]*)?\}\}")

# Flags belong to the command in their own pipeline stage; a deletion's target
# can arrive from an earlier stage (``ls ... | xargs rm``), so deletions are
# judged per statement.
SEGMENT_SPLIT_RE = re.compile(r"\|\||&&|[;|\n]")
STATEMENT_SPLIT_RE = re.compile(r"\|\||&&|[;\n]")
PODMAN_VOLUME_RM_RE = re.compile(r"\bpodman\s+volume\s+(?:rm|prune)\b")
PODMAN_SYSTEM_RESET_RE = re.compile(r"\bpodman\s+system\s+reset\b")
PODMAN_SYSTEM_PRUNE_RE = re.compile(r"\bpodman\s+system\s+prune\b")
PODMAN_RM_RE = re.compile(r"\bpodman\s+(?:container\s+)?rm\b")
PODMAN_POD_RM_RE = re.compile(r"\bpodman\s+pod\s+rm\b")
COMPOSE_DOWN_RE = re.compile(r"\bpodman(?:-|\s+)compose\b.*?\bdown\b")
# -v alone or inside a short-flag cluster (-fv, -vf), or --volume(s).
VOLUME_FLAG_RE = re.compile(r"(?:^|\s)(?:-[A-Za-z]*v[A-Za-z]*|--volumes?(?:=\S*)?)(?=\s|$)")
# rm as a command word, not as an argument (``podman rm`` is not file deletion).
RM_RE = re.compile(
    r"(?:^|[|(`]|\b(?:sudo|xargs|exec|command)\b)\s*(?:-\S+\s+)*(?:(?:/usr)?/bin/)?rm\s"
)
FIND_DELETE_RE = re.compile(r"\bfind\s.*(?:\s-delete\b|\s-exec\s+rm\b)")

PREFLIGHT_RE = re.compile(r"\bpodman\s+run\b(?=[^\n;|&]*\s--rm\b)")
CONTAINER_RM_RE = re.compile(r"\bpodman\s+(?:(?:container|pod)\s+)?rm\b")
TASK_LISTS = ("pre_tasks", "tasks", "post_tasks")
BLOCK_KEYS = ("block", "rescue", "always")

TRUTHY = {"true", "yes", "on", "1"}
MAX_RESOLVE_PASSES = 5


def _load(playbook_yaml: str) -> Any:
    import yaml

    try:
        document = yaml.safe_load(playbook_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"generated playbook is not valid YAML: {e}")

    if not isinstance(document, (dict, list)):
        raise ValueError("generated playbook is not a YAML mapping or list")
    return document


def scan_playbook(playbook_yaml: str) -> list[str]:
    """Return a list of violations; an empty list means the playbook is safe.

    Raises ``ValueError`` when the text is not parseable YAML or is not a
    playbook-shaped document, so the caller can distinguish "not a playbook"
    from "a playbook that must be rejected".
    """
    document = _load(playbook_yaml)
    variables = _collect_vars(document)
    violations = []
    violations.extend(_scan_structures(document, variables))
    violations.extend(_scan_strings(document, variables))
    return list(dict.fromkeys(violations))


def _collect_vars(node: Any, found: dict | None = None) -> dict[str, str]:
    """Flatten every scalar under a ``vars`` or ``set_fact`` mapping."""
    found = {} if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            name = str(key)
            if (name == "vars" or name.split(".")[-1] == "set_fact") and isinstance(value, dict):
                for var, var_value in value.items():
                    if isinstance(var_value, (str, int, float, bool)):
                        found[str(var)] = str(var_value)
            _collect_vars(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_vars(item, found)
    return found


def _resolve(text: str, variables: dict[str, str]) -> str:
    text = HOME_TEMPLATE_RE.sub("~", text)
    for _ in range(MAX_RESOLVE_PASSES):
        resolved = VAR_TEMPLATE_RE.sub(
            lambda m: variables.get(m.group(1), m.group(0)), text
        )
        resolved = HOME_TEMPLATE_RE.sub("~", resolved)
        if resolved == text:
            break
        text = resolved
    return text


def _scan_structures(node: Any, variables: dict[str, str]) -> list[str]:
    """Walk the parsed YAML looking for destructive module invocations."""
    violations = []
    if isinstance(node, dict):
        for key, value in node.items():
            name = str(key)
            short = name.split(".")[-1]
            if short == "podman_volume" and isinstance(value, dict):
                if str(value.get("state", "")).lower() == "absent":
                    violations.append(
                        f"task removes a podman volume via {name} with state: absent"
                    )
            if short == "podman_prune" and isinstance(value, dict):
                for option in ("volume", "system_volumes"):
                    if _truthy(value.get(option), variables):
                        violations.append(f"task prunes volumes via {name} {option}: true")
            if short == "file" and isinstance(value, dict):
                if str(value.get("state", "")).lower() == "absent":
                    target = _resolve(
                        str(value.get("path") or value.get("dest") or value.get("name") or ""),
                        variables,
                    )
                    reason = _unsafe_target(target)
                    if reason:
                        violations.append(
                            f"task deletes {reason} via {name} state: absent on {target}"
                        )
            violations.extend(_scan_structures(value, variables))
    elif isinstance(node, list):
        for item in node:
            violations.extend(_scan_structures(item, variables))
    return violations


def _scan_strings(node: Any, variables: dict[str, str]) -> list[str]:
    """Regex pass over every string in the document."""
    violations = []
    if isinstance(node, dict):
        for value in node.values():
            violations.extend(_scan_strings(value, variables))
    elif isinstance(node, list):
        for item in node:
            violations.extend(_scan_strings(item, variables))
        # An argv-style list of strings is one command line; "-v" only means
        # "remove volumes" in the presence of the podman command around it.
        if node and all(isinstance(item, str) for item in node):
            violations.extend(_check_command(" ".join(node), variables))
    elif isinstance(node, str):
        violations.extend(_check_command(node, variables))
    return violations


def _check_command(text: str, variables: dict[str, str]) -> list[str]:
    violations = []
    resolved = _resolve(text, variables)
    shown = resolved.strip()[:120]
    for segment in SEGMENT_SPLIT_RE.split(resolved):
        if PODMAN_VOLUME_RM_RE.search(segment):
            violations.append(f"command removes podman volumes: {shown}")
        if PODMAN_SYSTEM_RESET_RE.search(segment):
            violations.append(f"command resets podman storage including volumes: {shown}")
        for command_re, what in (
            (PODMAN_SYSTEM_PRUNE_RE, "podman system prune"),
            (PODMAN_RM_RE, "podman rm"),
            (PODMAN_POD_RM_RE, "podman pod rm"),
            (COMPOSE_DOWN_RE, "podman compose down"),
        ):
            match = command_re.search(segment)
            if match and VOLUME_FLAG_RE.search(segment[match.end():]):
                violations.append(f"command removes volumes via {what} -v/--volumes: {shown}")
    for statement in STATEMENT_SPLIT_RE.split(resolved):
        if RM_RE.search(statement) or FIND_DELETE_RE.search(statement):
            reason = _unsafe_statement(statement)
            if reason:
                violations.append(f"command deletes {reason}: {shown}")
    return violations


def _unsafe_statement(statement: str) -> str | None:
    """Why a deleting command statement is unsafe, or None when it is not."""
    if _targets_volume_data(statement):
        return "volume data"
    if "{{" in statement:
        return "an unresolved templated path"
    for token in statement.split():
        if _is_volume_ancestor(token):
            return f"a directory containing volume data ({token})"
    return None


def _unsafe_target(path: str) -> str | None:
    """Why deleting a single path is unsafe, or None when it is not."""
    if _targets_volume_data(path):
        return "volume data"
    if "{{" in path:
        return "an unresolved templated path"
    if _is_volume_ancestor(path):
        return "a directory containing volume data"
    return None


def _targets_volume_data(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in VOLUME_DATA_MARKERS)


def _is_volume_ancestor(token: str) -> bool:
    path = token.strip("'\"")
    path = path.rstrip("/") or ("/" if path.startswith("/") else "")
    return bool(path) and bool(VOLUME_ANCESTOR_RE.match(path))


def _truthy(value: Any, variables: dict[str, str]) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = _resolve(str(value), variables).strip().lower()
    # An option the guard cannot resolve might be true at runtime.
    return text in TRUTHY or "{{" in text


def scan_outage(playbook_yaml: str) -> list[str]:
    """Reject removal or recreation of a container or pod before a test run.

    Tasks are read in execution order per play, descending into blocks. A task
    that test-runs an image (a ``podman run --rm`` command, or a
    ``podman_container`` with ``rm: true``) proves the replacement for every
    task after it. Raises ``ValueError`` like :func:`scan_playbook`.
    """
    document = _load(playbook_yaml)
    variables = _collect_vars(document)
    plays = document if isinstance(document, list) else [document]
    violations = []
    for play in plays:
        if not isinstance(play, dict):
            continue
        proven = False
        for key in TASK_LISTS:
            for task in _flatten_tasks(play.get(key)):
                removal = _removal(task, variables)
                if removal and not proven:
                    violations.append(
                        f"task '{task.get('name', 'unnamed')}' {removal} before any earlier "
                        "task test-runs the replacement image (podman run --rm <image> ...); "
                        "a failed create would leave the service down"
                    )
                if _is_preflight(task, variables):
                    proven = True
    return violations


def _flatten_tasks(tasks: Any) -> list[dict]:
    flat = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        if any(key in task for key in BLOCK_KEYS):
            for key in BLOCK_KEYS:
                flat.extend(_flatten_tasks(task.get(key)))
        else:
            flat.append(task)
    return flat


def _task_text(task: dict, variables: dict[str, str]) -> str:
    """Every string in a task except its name, variables resolved."""
    parts = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            parts.append(node)

    walk({key: value for key, value in task.items() if key != "name"})
    return _resolve("\n".join(parts), variables)


def _is_preflight(task: dict, variables: dict[str, str]) -> bool:
    for key, value in task.items():
        if str(key).split(".")[-1] == "podman_container" and isinstance(value, dict):
            if _truthy(value.get("rm"), variables) and str(value.get("state", "")) != "absent":
                return True
    return bool(PREFLIGHT_RE.search(_task_text(task, variables)))


def _removal(task: dict, variables: dict[str, str]) -> str | None:
    for key, value in task.items():
        short = str(key).split(".")[-1]
        if short in ("podman_container", "podman_pod") and isinstance(value, dict):
            kind = "container" if short == "podman_container" else "pod"
            name = value.get("name", "?")
            if str(value.get("state", "")).lower() == "absent":
                return f"removes {kind} {name}"
            if _truthy(value.get("recreate"), variables):
                return f"recreates {kind} {name} (remove, then create)"
    text = _task_text(task, variables)
    for segment in SEGMENT_SPLIT_RE.split(text):
        if CONTAINER_RM_RE.search(segment):
            return f"removes a container or pod ({segment.strip()[:80]})"
        if COMPOSE_DOWN_RE.search(segment):
            return f"tears down a compose project ({segment.strip()[:80]})"
    return None
