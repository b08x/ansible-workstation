#!/usr/bin/env python3
"""Read-only audit harness for Syncopated Workstation Ansible role variables.

Enforces the six deterministic variable hygiene rules (R1-R6) and optional
Sandi Metz modularity budgets defined in
``goals/role-variable-audit-refactor/design.md`` (Section 7):

- R1 (``unused-default``): Every key in ``roles/<role>/defaults/main.yml`` is
  referenced in ``tasks/``, ``handlers/``, or ``templates/``.
- R2 (``vars-shadow-default``): Zero key overlap between ``defaults/main.yml``
  and ``vars/*.yml``.
- R3 (``tier2-naming``): ``defaults/main.yml`` keys start with ``<role>_``;
  ``vars/main.yml`` keys start with ``_<role>_``; distro ``vars/*.yml`` keys
  start with ``_<role>_distro_``.
- R4 (``private-var-naming``): Every ``register:`` and ``set_fact`` key across
  ``tasks/`` and ``handlers/`` starts with ``_<role>_``, except the six
  allowlisted Tier 1 hardware capability facts in
  ``roles/common/tasks/hardware.yml``.
- R5 (``argspec-parity``): ``meta/argument_specs.yml`` exists, its
  ``argument_specs.main.options`` keys equal ``defaults/main.yml`` keys, and
  required enum selectors declare exact ``choices`` lists.
- R6 (``retired-variable-reference``): Zero references to retired variable
  patterns in scanned roles (and repo-wide inventory, playbooks, ``local.yml``,
  plus absence of ``roles/desktop_ui`` when no ``--role`` filter is given).
- MOD (``modularity-budget``, optional ``--check-modularity``): Every task YAML
  file has at most 100 lines and at most 10 tasks (top-level and leaf).

Exit codes:
    0: Zero violations detected.
    1: One or more audit rule violations detected.
    2: CLI usage error, unknown role, missing ``roles/`` directory, or YAML error.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "MAX_TASKS_PER_FILE",
    "MAX_TASK_FILE_LINES",
    "REQUIRED_ENUM_CHOICES",
    "RETIRED_VAR_PATTERNS",
    "TIER1_HARDWARE_FACT_ALLOWLIST",
    "AuditError",
    "AuditReport",
    "Violation",
    "audit_repository",
    "main",
]

MAX_TASK_FILE_LINES: int = 100
MAX_TASKS_PER_FILE: int = 10

TIER1_HARDWARE_FACT_ALLOWLIST: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("common", "tasks/hardware.yml", "detected_gpu_vendor"),
        ("common", "tasks/hardware.yml", "has_cuda"),
        ("common", "tasks/hardware.yml", "has_vulkan"),
        ("common", "tasks/hardware.yml", "is_virtual_guest"),
        ("common", "tasks/hardware.yml", "detected_chassis_type"),
        ("common", "tasks/hardware.yml", "recommended_tuned_profile"),
    }
)

REQUIRED_ENUM_CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("sway", "sway_bar_engine"): ("eww", "waybar"),
    ("sway", "sway_compositor"): ("swayfx", "sway"),
    ("containerd", "containerd_engine"): ("podman", "docker", "none"),
    ("tools", "tools_vscode_install_method"): ("none", "rpm", "flatpak"),
    ("theme", "theme_name"): ("yaru", "none"),
    ("cosmic", "cosmic_display_manager"): ("cosmic-greeter", "gdm"),
}

RETIRED_VAR_PATTERNS: tuple[tuple[str, str], ...] = (
    ("sway_use_eww", r"\bsway_use_eww\b"),
    ("sway_use_swayfx", r"\bsway_use_swayfx\b"),
    ("swayfx_*", r"\bswayfx_[a-z0-9_]+\b"),
    ("sway_copr_repositories", r"\bsway_copr_repositories\b"),
    ("sway_force_reconfigure", r"\bsway_force_reconfigure\b"),
    ("sway_volume_notifications", r"\bsway_volume_notifications\b"),
    ("containerd_use_podman", r"\bcontainerd_use_podman\b"),
    ("containerd_use_docker", r"\bcontainerd_use_docker\b"),
    (
        "containerd_docker_remove_conflicting_packages",
        r"\bcontainerd_docker_remove_conflicting_packages\b",
    ),
    ("tools_install_vscode", r"\btools_install_vscode\b"),
    ("tools_vscode_flatpak", r"\btools_vscode_flatpak\b"),
    ("enable_desktop", r"\benable_desktop\b"),
    ("desktop_ui*", r"\bdesktop_ui(?:_[a-z0-9_]+)?\b"),
    ("nvidia_cuda_install", r"\bnvidia_cuda_install\b"),
    ("intel_oneapi_install", r"\bintel_oneapi_install\b"),
    ("enable_firstboot", r"\benable_firstboot\b"),
    ("use_containers", r"\buse_containers\b"),
    ("use_kvm", r"\buse_kvm\b"),
    ("osbuild_*components", r"\bosbuild_(?:[a-z0-9_]+_)?components\b"),
    ("*_my_variable", r"\b[a-z0-9_]+_my_variable\b"),
    ("common_gitflow_copr_fedora", r"\bcommon_gitflow_copr_fedora\b"),
    ("nas_rsync_uid", r"\bnas_rsync_uid\b"),
    ("nas_rsync_gid", r"\bnas_rsync_gid\b"),
    ("firewall.nfs", r"\bfirewall\.nfs\b"),
)

_COMPILED_RETIRED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern, re.MULTILINE)) for label, pattern in RETIRED_VAR_PATTERNS
)
_YAML_SUFFIXES: frozenset[str] = frozenset({".yml", ".yaml"})
_R6_ROLE_SUFFIXES: frozenset[str] = frozenset({".yml", ".yaml", ".j2"})
_R1_CORPUS_SUBDIRS: tuple[str, ...] = ("tasks", "handlers", "templates")
_R6_ROLE_SUBDIRS: tuple[str, ...] = (
    "defaults",
    "vars",
    "tasks",
    "handlers",
    "templates",
    "meta",
)
_SET_FACT_KEYS: frozenset[str] = frozenset(
    {"set_fact", "ansible.builtin.set_fact", "ansible.legacy.set_fact"}
)
_BLOCK_SECTIONS: tuple[str, ...] = ("block", "rescue", "always")
_RULE_METADATA: tuple[tuple[str, str], ...] = (
    ("R1", "unused-default"),
    ("R2", "vars-shadow-default"),
    ("R3", "tier2-naming"),
    ("R4", "private-var-naming"),
    ("R5", "argspec-parity"),
    ("R6", "retired-variable-reference"),
    ("MOD", "modularity-budget"),
)
_RULE_ORDER: dict[str, int] = {rule: index for index, (rule, _) in enumerate(_RULE_METADATA)}


class AuditError(Exception):
    """Raised when the audit cannot run due to configuration or YAML errors."""


@dataclass(frozen=True)
class Violation:
    """Single rule violation discovered during a repository audit.

    Attributes:
        rule: Short rule identifier (``R1``-``R6`` or ``MOD``).
        code: Machine-readable rule slug (for example ``unused-default``).
        path: POSIX path relative to the repository root.
        message: Human-readable explanation of the violation.
        role: Role name when scoped to a role, or ``None`` for repo-wide files.
        line: 1-based line number when applicable, otherwise ``None``.
        symbol: Variable name or matched identifier when applicable.
    """

    rule: str
    code: str
    path: str
    message: str
    role: str | None = None
    line: int | None = None
    symbol: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the violation into a JSON-compatible dictionary.

        Returns:
            Dictionary containing all violation fields.
        """
        return {
            "rule": self.rule,
            "code": self.code,
            "role": self.role,
            "path": self.path,
            "line": self.line,
            "symbol": self.symbol,
            "message": self.message,
        }


@dataclass(frozen=True)
class AuditReport:
    """Complete result of an audit run.

    Attributes:
        repo_root: Resolved path string to the audited repository root.
        roles_audited: Ordered tuple of audited role names.
        repo_wide: Whether repo-wide inventory/playbooks/local.yml checks ran.
        check_modularity: Whether Sandi Metz modularity checks ran.
        violations: Sorted tuple of detected violations.
    """

    repo_root: str
    roles_audited: tuple[str, ...]
    repo_wide: bool
    check_modularity: bool
    violations: tuple[Violation, ...]

    def summary_by_rule(self) -> dict[str, int]:
        """Count violations per enabled rule identifier.

        Returns:
            Mapping from rule identifier (``R1``-``R6``, plus ``MOD`` if enabled)
            to the count of matching violations.
        """
        counts: dict[str, int] = {
            rule: 0 for rule, _ in _RULE_METADATA if rule != "MOD" or self.check_modularity
        }
        for violation in self.violations:
            counts[violation.rule] = counts.get(violation.rule, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full audit report into a JSON-compatible dictionary.

        Returns:
            Dictionary with scope metadata, per-rule counts, and violations.
        """
        return {
            "repo_root": self.repo_root,
            "roles_audited": list(self.roles_audited),
            "repo_wide": self.repo_wide,
            "check_modularity": self.check_modularity,
            "total_violations": len(self.violations),
            "summary": self.summary_by_rule(),
            "violations": [violation.to_dict() for violation in self.violations],
        }


def _rel_posix(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` formatted with POSIX separators."""
    return path.relative_to(root).as_posix()


def _iter_files(
    directory: Path,
    suffixes: frozenset[str] | None = None,
) -> list[Path]:
    """Return sorted regular files recursively under ``directory``.

    Args:
        directory: Directory to traverse.
        suffixes: Optional set of lowercase file suffixes (including leading dot)
            used to filter results.

    Returns:
        Sorted list of matching file paths, or an empty list if ``directory``
        does not exist.
    """
    if not directory.is_dir():
        return []
    matches: list[Path] = []
    for candidate in sorted(directory.rglob("*")):
        if not candidate.is_file():
            continue
        if suffixes is not None and candidate.suffix.lower() not in suffixes:
            continue
        matches.append(candidate)
    return matches


def _load_yaml(path: Path, repo_root: Path) -> Any:
    """Load and parse a UTF-8 YAML file.

    Args:
        path: Path to the YAML file.
        repo_root: Repository root for error reporting.

    Returns:
        Parsed YAML object (which may be ``None`` for empty documents).

    Raises:
        AuditError: If the file cannot be read or contains invalid YAML.
    """
    rel_path = _rel_posix(path, repo_root)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditError(f"Failed to read {rel_path}: {exc}") from exc
    try:
        return yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise AuditError(f"YAML syntax error in {rel_path}: {exc}") from exc


def _load_yaml_mapping(path: Path, repo_root: Path) -> dict[str, Any]:
    """Load a YAML file expected to contain a top-level mapping or empty document.

    Args:
        path: Path to the YAML file.
        repo_root: Repository root for error reporting.

    Returns:
        Dictionary of top-level keys to values.

    Raises:
        AuditError: If the YAML file cannot be parsed or is not a mapping.
    """
    data = _load_yaml(path, repo_root)
    if data is None:
        return {}
    if not isinstance(data, dict):
        rel_path = _rel_posix(path, repo_root)
        raise AuditError(f"Expected YAML mapping in {rel_path}, got {type(data).__name__}.")
    return {str(key): value for key, value in data.items()}


def _load_yaml_task_list(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    """Load a YAML task or handler file expected to contain a task list.

    Args:
        path: Path to the task or handler YAML file.
        repo_root: Repository root for error reporting.

    Returns:
        List of task dictionaries.

    Raises:
        AuditError: If the YAML file cannot be parsed or is not a list.
    """
    data = _load_yaml(path, repo_root)
    if data is None:
        return []
    if not isinstance(data, list):
        rel_path = _rel_posix(path, repo_root)
        raise AuditError(f"Expected YAML task list in {rel_path}, got {type(data).__name__}.")
    return [item for item in data if isinstance(item, dict)]


def _walk_tasks(items: Sequence[Any]) -> Iterable[dict[str, Any]]:
    """Recursively yield every task mapping including nested block sections.

    Args:
        items: Sequence of parsed YAML task entries.

    Yields:
        Each task dictionary in document order.
    """
    for item in items:
        if not isinstance(item, dict):
            continue
        yield item
        for section in _BLOCK_SECTIONS:
            nested = item.get(section)
            if isinstance(nested, list):
                yield from _walk_tasks(nested)


def _count_leaf_tasks(items: Sequence[Any]) -> int:
    """Count executable leaf tasks recursively inside a YAML task list.

    Block containers (dictionaries with ``block``, ``rescue``, or ``always``
    lists) are expanded so their nested tasks are counted instead of the
    container itself.

    Args:
        items: Sequence of parsed YAML task entries.

    Returns:
        Total number of leaf tasks.
    """
    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        has_block = any(isinstance(item.get(section), list) for section in _BLOCK_SECTIONS)
        if has_block:
            for section in _BLOCK_SECTIONS:
                nested = item.get(section)
                if isinstance(nested, list):
                    total += _count_leaf_tasks(nested)
        else:
            total += 1
    return total


def _extract_set_fact_keys(raw_value: Any) -> list[str]:
    """Extract declared fact names from a ``set_fact`` module argument.

    Supports both standard YAML mapping syntax and legacy free-form
    ``key=value`` string arguments, excluding the reserved ``cacheable`` option.

    Args:
        raw_value: Value assigned to ``set_fact`` or ``ansible.builtin.set_fact``.

    Returns:
        List of fact variable names declared by the task.
    """
    if isinstance(raw_value, dict):
        return [str(key) for key in raw_value if str(key) != "cacheable"]
    if isinstance(raw_value, str):
        keys: list[str] = []
        try:
            tokens = shlex.split(raw_value)
        except ValueError:
            tokens = raw_value.split()
        for token in tokens:
            if "=" not in token:
                continue
            key = token.split("=", 1)[0].strip()
            if key and key != "cacheable":
                keys.append(key)
        return keys
    return []


def _find_defaults_file(role_dir: Path) -> Path | None:
    """Locate ``defaults/main.yml`` (or ``.yaml``) for a role if present."""
    for filename in ("main.yml", "main.yaml"):
        candidate = role_dir / "defaults" / filename
        if candidate.is_file():
            return candidate
    return None


def _check_r1_unused_defaults(
    role: str,
    role_dir: Path,
    defaults_file: Path | None,
    defaults: Mapping[str, Any],
    repo_root: Path,
) -> list[Violation]:
    """Enforce R1: every default key is referenced in tasks, handlers, or templates."""
    if not defaults or defaults_file is None:
        return []
    corpus_parts: list[str] = []
    for subdir in _R1_CORPUS_SUBDIRS:
        for file_path in _iter_files(role_dir / subdir):
            try:
                corpus_parts.append(file_path.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                rel_path = _rel_posix(file_path, repo_root)
                raise AuditError(f"Failed to read {rel_path}: {exc}") from exc
    corpus = "\n".join(corpus_parts)
    defaults_rel = _rel_posix(defaults_file, repo_root)
    violations: list[Violation] = []
    for key in sorted(defaults):
        if re.search(rf"\b{re.escape(key)}\b", corpus) is None:
            violations.append(
                Violation(
                    rule="R1",
                    code="unused-default",
                    role=role,
                    path=defaults_rel,
                    symbol=key,
                    message=(
                        f"Default variable '{key}' is not referenced in "
                        f"roles/{role}/{{tasks,handlers,templates}}/."
                    ),
                )
            )
    return violations


def _check_r2_r3_vars_and_defaults(
    role: str,
    role_dir: Path,
    defaults_file: Path | None,
    defaults: Mapping[str, Any],
    repo_root: Path,
) -> list[Violation]:
    """Enforce R2 (vars shadowing defaults) and R3 (Tier 2 variable naming)."""
    violations: list[Violation] = []
    default_prefix = f"{role}_"
    if defaults_file is not None:
        defaults_rel = _rel_posix(defaults_file, repo_root)
        for key in sorted(defaults):
            if not key.startswith(default_prefix):
                violations.append(
                    Violation(
                        rule="R3",
                        code="tier2-naming",
                        role=role,
                        path=defaults_rel,
                        symbol=key,
                        message=f"Default variable '{key}' must start with '{default_prefix}'.",
                    )
                )

    vars_dir = role_dir / "vars"
    for vars_file in _iter_files(vars_dir, _YAML_SUFFIXES):
        vars_data = _load_yaml_mapping(vars_file, repo_root)
        vars_rel = _rel_posix(vars_file, repo_root)
        is_main = vars_file.name in {"main.yml", "main.yaml"}
        required_prefix = f"_{role}_" if is_main else f"_{role}_distro_"
        for key in sorted(vars_data):
            if key in defaults:
                violations.append(
                    Violation(
                        rule="R2",
                        code="vars-shadow-default",
                        role=role,
                        path=vars_rel,
                        symbol=key,
                        message=f"Variable '{key}' in {vars_file.name} shadows defaults/main.yml.",
                    )
                )
            if not key.startswith(required_prefix):
                violations.append(
                    Violation(
                        rule="R3",
                        code="tier2-naming",
                        role=role,
                        path=vars_rel,
                        symbol=key,
                        message=(
                            f"Vars key '{key}' in {vars_file.name} must start with "
                            f"'{required_prefix}'."
                        ),
                    )
                )
    return violations


def _check_r4_private_vars(
    role: str,
    role_dir: Path,
    repo_root: Path,
) -> list[Violation]:
    """Enforce R4: private ``_<role>_`` prefix on all registers and set_fact keys."""
    violations: list[Violation] = []
    required_prefix = f"_{role}_"
    for subdir in ("tasks", "handlers"):
        for task_file in _iter_files(role_dir / subdir, _YAML_SUFFIXES):
            tasks = _load_yaml_task_list(task_file, repo_root)
            rel_path = _rel_posix(task_file, repo_root)
            rel_in_role = task_file.relative_to(role_dir).as_posix()
            for task in _walk_tasks(tasks):
                registered = task.get("register")
                if isinstance(registered, str):
                    reg_name = registered.strip()
                    if reg_name and not reg_name.startswith(required_prefix):
                        violations.append(
                            Violation(
                                rule="R4",
                                code="private-var-naming",
                                role=role,
                                path=rel_path,
                                symbol=reg_name,
                                message=(
                                    f"Registered variable '{reg_name}' must start "
                                    f"with '{required_prefix}'."
                                ),
                            )
                        )
                for sf_module in _SET_FACT_KEYS:
                    if sf_module not in task:
                        continue
                    for fact_key in _extract_set_fact_keys(task[sf_module]):
                        if (role, rel_in_role, fact_key) in TIER1_HARDWARE_FACT_ALLOWLIST:
                            continue
                        if not fact_key.startswith(required_prefix):
                            violations.append(
                                Violation(
                                    rule="R4",
                                    code="private-var-naming",
                                    role=role,
                                    path=rel_path,
                                    symbol=fact_key,
                                    message=(
                                        f"set_fact variable '{fact_key}' must start "
                                        f"with '{required_prefix}'."
                                    ),
                                )
                            )
    return violations


def _check_r5_argspec_parity(
    role: str,
    role_dir: Path,
    defaults: Mapping[str, Any],
    repo_root: Path,
) -> list[Violation]:
    """Enforce R5: argument_specs.yml existence, 100% key parity, and enum choices."""
    argspec_path = role_dir / "meta" / "argument_specs.yml"
    argspec_rel = _rel_posix(argspec_path, repo_root)
    if not argspec_path.is_file():
        return [
            Violation(
                rule="R5",
                code="argspec-parity",
                role=role,
                path=argspec_rel,
                message=f"Missing required role argument specification file '{argspec_rel}'.",
            )
        ]

    parsed = _load_yaml(argspec_path, repo_root)
    argument_specs = parsed.get("argument_specs") if isinstance(parsed, dict) else None
    main_spec = argument_specs.get("main") if isinstance(argument_specs, dict) else None
    options = main_spec.get("options") if isinstance(main_spec, dict) else None
    if not isinstance(options, dict):
        return [
            Violation(
                rule="R5",
                code="argspec-parity",
                role=role,
                path=argspec_rel,
                message="Expected mapping at 'argument_specs.main.options'.",
            )
        ]

    violations: list[Violation] = []
    default_keys = set(defaults.keys())
    option_keys = {str(key) for key in options}

    for missing_key in sorted(default_keys - option_keys):
        violations.append(
            Violation(
                rule="R5",
                code="argspec-parity",
                role=role,
                path=argspec_rel,
                symbol=missing_key,
                message=(
                    f"Default variable '{missing_key}' is missing from "
                    "argument_specs.main.options."
                ),
            )
        )

    for extra_key in sorted(option_keys - default_keys):
        violations.append(
            Violation(
                rule="R5",
                code="argspec-parity",
                role=role,
                path=argspec_rel,
                symbol=extra_key,
                message=f"Argument spec option '{extra_key}' does not exist in defaults/main.yml.",
            )
        )

    for (req_role, req_var), expected_choices in REQUIRED_ENUM_CHOICES.items():
        if req_role != role:
            continue
        opt_spec = options.get(req_var)
        expected_list = list(expected_choices)
        if not isinstance(opt_spec, dict):
            violations.append(
                Violation(
                    rule="R5",
                    code="argspec-parity",
                    role=role,
                    path=argspec_rel,
                    symbol=req_var,
                    message=(
                        f"Required enum selector '{req_var}' is missing from "
                        f"argument_specs.main.options (expected choices: {expected_list})."
                    ),
                )
            )
            continue
        raw_choices = opt_spec.get("choices")
        valid_choices = (
            isinstance(raw_choices, list)
            and all(isinstance(choice, str) for choice in raw_choices)
            and len(raw_choices) == len(expected_choices)
            and set(raw_choices) == set(expected_choices)
        )
        if not valid_choices:
            violations.append(
                Violation(
                    rule="R5",
                    code="argspec-parity",
                    role=role,
                    path=argspec_rel,
                    symbol=req_var,
                    message=(
                        f"Enum selector '{req_var}' must declare choices "
                        f"{sorted(expected_list)}, found {raw_choices!r}."
                    ),
                )
            )

    return violations


def _scan_file_retired_vars(
    path: Path,
    repo_root: Path,
    role: str | None,
) -> list[Violation]:
    """Scan a single text file line-by-line for retired variable patterns (R6)."""
    rel_path = _rel_posix(path, repo_root)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise AuditError(f"Failed to read {rel_path}: {exc}") from exc

    violations: list[Violation] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for label, compiled_regex in _COMPILED_RETIRED_PATTERNS:
            match = compiled_regex.search(line)
            if match is None:
                continue
            matched_text = match.group(0)
            violations.append(
                Violation(
                    rule="R6",
                    code="retired-variable-reference",
                    role=role,
                    path=rel_path,
                    line=lineno,
                    symbol=matched_text,
                    message=f"Retired variable pattern '{label}' matched '{matched_text}'.",
                )
            )
    return violations


def _check_r6_role(role: str, role_dir: Path, repo_root: Path) -> list[Violation]:
    """Enforce R6 across a single role's YAML and Jinja2 files."""
    violations: list[Violation] = []
    for subdir in _R6_ROLE_SUBDIRS:
        for file_path in _iter_files(role_dir / subdir, _R6_ROLE_SUFFIXES):
            violations.extend(_scan_file_retired_vars(file_path, repo_root, role=role))
    return violations


def _check_r6_repo_wide(repo_root: Path) -> list[Violation]:
    """Enforce R6 on inventory, playbooks, local.yml, and retired role removal."""
    violations: list[Violation] = []

    desktop_ui_dir = repo_root / "roles" / "desktop_ui"
    if desktop_ui_dir.exists():
        violations.append(
            Violation(
                rule="R6",
                code="retired-variable-reference",
                role="desktop_ui",
                path=_rel_posix(desktop_ui_dir, repo_root),
                symbol="desktop_ui",
                message=(
                    "Retired role directory 'roles/desktop_ui' still exists "
                    "(must be split into theme, gnome, and cosmic and removed)."
                ),
            )
        )

    for inv_subdir in ("group_vars", "host_vars"):
        inv_dir = repo_root / "inventory" / inv_subdir
        for file_path in _iter_files(inv_dir, _YAML_SUFFIXES):
            violations.extend(_scan_file_retired_vars(file_path, repo_root, role=None))

    playbooks_dir = repo_root / "playbooks"
    for file_path in _iter_files(playbooks_dir, _YAML_SUFFIXES):
        rel_parts = file_path.relative_to(playbooks_dir).parts
        if rel_parts and rel_parts[0] == "_argspec":
            continue
        violations.extend(_scan_file_retired_vars(file_path, repo_root, role=None))

    local_playbook = repo_root / "local.yml"
    if local_playbook.is_file():
        violations.extend(_scan_file_retired_vars(local_playbook, repo_root, role=None))

    return violations


def _check_modularity(role: str, role_dir: Path, repo_root: Path) -> list[Violation]:
    """Enforce Sandi Metz budgets (<=100 lines, <=10 top-level/leaf tasks)."""
    violations: list[Violation] = []
    for task_file in _iter_files(role_dir / "tasks", _YAML_SUFFIXES):
        rel_path = _rel_posix(task_file, repo_root)
        try:
            raw_text = task_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise AuditError(f"Failed to read {rel_path}: {exc}") from exc
        line_count = len(raw_text.splitlines())
        if line_count > MAX_TASK_FILE_LINES:
            violations.append(
                Violation(
                    rule="MOD",
                    code="modularity-budget",
                    role=role,
                    path=rel_path,
                    message=f"Task file has {line_count} lines (budget: <= {MAX_TASK_FILE_LINES}).",
                )
            )
        tasks = _load_yaml_task_list(task_file, repo_root)
        top_count = len(tasks)
        leaf_count = _count_leaf_tasks(tasks)
        if top_count > MAX_TASKS_PER_FILE or leaf_count > MAX_TASKS_PER_FILE:
            violations.append(
                Violation(
                    rule="MOD",
                    code="modularity-budget",
                    role=role,
                    path=rel_path,
                    message=(
                        f"Task file has {top_count} top-level / {leaf_count} leaf "
                        f"tasks (budget: <= {MAX_TASKS_PER_FILE})."
                    ),
                )
            )
    return violations


def _resolve_roles(
    repo_root: Path,
    requested_roles: Sequence[str] | None,
) -> tuple[list[str], bool]:
    """Validate and resolve the ordered list of role names to audit.

    Args:
        repo_root: Resolved repository root path.
        requested_roles: Optional sequence of ``--role`` arguments.

    Returns:
        Tuple of ``(role_names, is_repo_wide)``.

    Raises:
        AuditError: If ``roles/`` is missing or a requested role does not exist.
    """
    roles_dir = repo_root / "roles"
    if not roles_dir.is_dir():
        raise AuditError(f"Roles directory not found: {roles_dir}")

    if not requested_roles:
        discovered = sorted(
            entry.name
            for entry in roles_dir.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
        return discovered, True

    unique_roles: list[str] = []
    seen: set[str] = set()
    for role_name in requested_roles:
        if role_name in seen:
            continue
        if (
            not role_name
            or role_name.startswith(".")
            or Path(role_name).name != role_name
            or not (roles_dir / role_name).is_dir()
        ):
            raise AuditError(f"Unknown role '{role_name}': expected directory under {roles_dir}.")
        seen.add(role_name)
        unique_roles.append(role_name)
    return unique_roles, False


def audit_repository(
    repo_root: Path,
    roles: Sequence[str] | None = None,
    check_modularity: bool = False,
) -> AuditReport:
    """Run all configured variable hygiene rules against an Ansible repository.

    Args:
        repo_root: Path to the repository root containing ``roles/``.
        roles: Optional list of role names to scope the audit. When ``None`` or
            empty, audits all roles plus inventory, playbooks, and ``local.yml``.
        check_modularity: When ``True``, also validates task file line and task
            count budgets (<= 100 lines, <= 10 top-level and leaf tasks).

    Returns:
        Frozen ``AuditReport`` containing scope metadata and sorted violations.

    Raises:
        AuditError: On missing ``roles/``, unknown role names, I/O errors, or
            invalid YAML syntax.
    """
    resolved_root = repo_root.resolve()
    target_roles, repo_wide = _resolve_roles(resolved_root, roles)
    violations: list[Violation] = []

    for role in target_roles:
        role_dir = resolved_root / "roles" / role
        defaults_file = _find_defaults_file(role_dir)
        defaults = (
            _load_yaml_mapping(defaults_file, resolved_root) if defaults_file is not None else {}
        )
        violations.extend(
            _check_r1_unused_defaults(role, role_dir, defaults_file, defaults, resolved_root)
        )
        violations.extend(
            _check_r2_r3_vars_and_defaults(role, role_dir, defaults_file, defaults, resolved_root)
        )
        violations.extend(_check_r4_private_vars(role, role_dir, resolved_root))
        violations.extend(_check_r5_argspec_parity(role, role_dir, defaults, resolved_root))
        violations.extend(_check_r6_role(role, role_dir, resolved_root))
        if check_modularity:
            violations.extend(_check_modularity(role, role_dir, resolved_root))

    if repo_wide:
        violations.extend(_check_r6_repo_wide(resolved_root))

    sorted_violations = tuple(
        sorted(
            violations,
            key=lambda item: (
                _RULE_ORDER.get(item.rule, 99),
                item.path,
                item.line or 0,
                item.symbol or "",
                item.message,
            ),
        )
    )
    return AuditReport(
        repo_root=str(resolved_root),
        roles_audited=tuple(target_roles),
        repo_wide=repo_wide,
        check_modularity=check_modularity,
        violations=sorted_violations,
    )


def _format_text_report(report: AuditReport) -> str:
    """Format an ``AuditReport`` as grouped human-readable text."""
    lines: list[str] = []
    scope_label = "repo-wide" if report.repo_wide else f"roles={','.join(report.roles_audited)}"
    mod_label = "on" if report.check_modularity else "off"

    if not report.violations:
        lines.append(
            f"PASS: 0 violations across {len(report.roles_audited)} role(s) "
            f"({scope_label}, modularity={mod_label})."
        )
        return "\n".join(lines)

    grouped: dict[str, list[Violation]] = {}
    for violation in report.violations:
        grouped.setdefault(violation.rule, []).append(violation)

    for rule, code in _RULE_METADATA:
        items = grouped.get(rule)
        if not items:
            continue
        lines.append(f"=== {rule} ({code}): {len(items)} violation(s) ===")
        for item in items:
            location = f"{item.path}:{item.line}" if item.line is not None else item.path
            lines.append(f"  {location}: {item.message}")
        lines.append("")

    summary = report.summary_by_rule()
    lines.append(
        f"Summary ({len(report.roles_audited)} role(s) audited, "
        f"scope={scope_label}, modularity={mod_label}):"
    )
    for rule, code in _RULE_METADATA:
        if rule not in summary:
            continue
        label = f"{rule} ({code}):"
        lines.append(f"  {label:<34} {summary[rule]}")
    lines.append(f"  {'Total violations:':<34} {len(report.violations)}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        prog="audit_role_vars.py",
        description=(
            "Audit Ansible role defaults, vars, tasks, handlers, argument specs, "
            "and retired variable references."
        ),
    )
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        metavar="NAME",
        help=(
            "Audit only the named role (repeatable). When omitted, audits all "
            "roles under roles/ plus inventory, playbooks, and local.yml."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_root,
        metavar="PATH",
        help=f"Path to the repository root directory (default: {default_root}).",
    )
    parser.add_argument(
        "--check-modularity",
        action="store_true",
        help=(
            f"Enforce Sandi Metz task file budgets (<= {MAX_TASK_FILE_LINES} lines "
            f"and <= {MAX_TASKS_PER_FILE} top-level/leaf tasks)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="Output format (default: text).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for the role variable audit harness.

    Args:
        argv: Optional command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit status code: ``0`` if clean, ``1`` if violations exist, ``2`` on
        runtime or configuration errors.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = audit_repository(
            repo_root=args.repo_root,
            roles=args.roles,
            check_modularity=args.check_modularity,
        )
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    output = (
        json.dumps(report.to_dict(), indent=2)
        if args.output_format == "json"
        else _format_text_report(report)
    )
    try:
        print(output)
    except BrokenPipeError:
        return 1 if report.violations else 0
    return 1 if report.violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
