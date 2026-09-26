# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Ansible style-guide checkers for llm_analyzer.

Every checker here is a pure function of the YAML text: no Ansible object, no
network, no shared state. That is what lets the whole style pass run on the
analyser's worker threads alongside the LLM call rather than on Ansible's main
thread (see ``CallbackModule._process``).

A violation is a plain dict::

    {"type": str, "message": str, "line": int, "reference": str (optional)}

``type`` is the join key to :mod:`llm_suggestions`, which maps each one to a
concrete edit.
"""

from __future__ import absolute_import, division, print_function

import re
from typing import Any

__metaclass__ = type


def analyze_style(yaml_content: str) -> list[dict[str, Any]]:
    """Analyze YAML content for Ansible style guide violations.

    Args:
        yaml_content: The YAML content to analyze

    Returns:
        List of violation dictionaries with type, message, and line info
    """
    violations = []
    lines = yaml_content.split("\n")

    violations.extend(_check_variable_naming(lines))
    violations.extend(_check_task_structure(lines))
    violations.extend(_check_tag_conventions(lines))
    violations.extend(_check_ansible_way_violations(lines))
    violations.extend(_check_role_design_violations(lines))
    violations.extend(_check_module_design_violations(yaml_content, lines))

    return violations


def _check_variable_naming(lines: list[str]) -> list[dict[str, Any]]:
    """Check for variable naming convention violations."""
    violations = []

    # Pattern for camelCase variables in Jinja templates
    camel_case_pattern = r"{{\s*([a-z][a-zA-Z]*[A-Z][a-zA-Z]*)\s*}}"

    # Pattern for variables in vars sections that start with capital letters
    vars_pattern = r"^\s*([A-Z][a-zA-Z]*)\s*:"

    for line_num, line in enumerate(lines, 1):
        # Check for camelCase in Jinja templates
        camel_matches = re.findall(camel_case_pattern, line)
        for match in camel_matches:
            violations.append(
                {
                    "type": "variable_naming",
                    "message": f'Variable "{match}" should use snake_case: "{to_snake_case(match)}"',
                    "line": line_num,
                }
            )

        # Check for variables starting with capital letters
        vars_match = re.match(vars_pattern, line)
        if vars_match:
            var_name = vars_match.group(1)
            violations.append(
                {
                    "type": "variable_naming",
                    "message": f'Variable "{var_name}" should use snake_case with role prefix',
                    "line": line_num,
                }
            )

    return violations


def _check_task_structure(lines: list[str]) -> list[dict[str, Any]]:
    """Check for task structure violations according to style guide.

    Expected order: name, module, become, loop, when, tags, notify
    """
    violations = []
    in_task = False
    task_start_line = 0
    task_attributes = []

    for line_num, line in enumerate(lines, 1):
        # Detect start of a task (starts with "- ")
        if re.match(r"^\s*-\s+\w+:", line):
            if in_task and task_attributes:
                # Check previous task structure
                violations.extend(_validate_task_attribute_order(task_attributes, task_start_line))

            in_task = True
            task_start_line = line_num
            task_attributes = []

            # Extract first attribute
            match = re.match(r"^\s*-\s+(\w+):", line)
            if match:
                task_attributes.append(match.group(1))

        # Collect other task attributes
        elif in_task and re.match(r"^\s+(\w+):", line):
            match = re.match(r"^\s+(\w+):", line)
            if match:
                attr = match.group(1)
                # Skip ansible module attributes (they're not task-level attributes)
                if not line.strip().startswith("ansible.builtin."):
                    task_attributes.append(attr)

        # End of task detection (empty line or new task/block)
        elif in_task and (line.strip() == "" or re.match(r"^\s*-|^\w+:", line)):
            if task_attributes:
                violations.extend(_validate_task_attribute_order(task_attributes, task_start_line))
            in_task = False
            task_attributes = []

    # Check last task if file ends while in task
    if in_task and task_attributes:
        violations.extend(_validate_task_attribute_order(task_attributes, task_start_line))

    return violations


def _validate_task_attribute_order(attributes: list[str], start_line: int) -> list[dict[str, Any]]:
    """Validate the order of task attributes against the style guide."""
    violations = []
    expected_order = ["name", "become", "loop", "when", "tags", "notify"]

    # Filter attributes to only those in expected order
    relevant_attrs = [attr for attr in attributes if attr in expected_order]

    if len(relevant_attrs) > 1:
        # Check if they're in the expected order
        sorted_attrs = sorted(relevant_attrs, key=lambda x: expected_order.index(x))
        if relevant_attrs != sorted_attrs:
            violations.append(
                {
                    "type": "task_structure",
                    "message": "Task attributes not in recommended order. Should be: name, module, become, loop, when, tags, notify",
                    "line": start_line,
                }
            )

    return violations


def _check_tag_conventions(lines: list[str]) -> list[dict[str, Any]]:
    """Check for tag naming convention violations."""
    violations = []

    for line_num, line in enumerate(lines, 1):
        # Check for string format tags (should be array)
        if re.search(r'tags:\s*"[^"]*"', line):
            violations.append(
                {
                    "type": "tag_naming",
                    "message": "Tags should use square bracket array format",
                    "line": line_num,
                }
            )

        # Check for single unquoted tags (should be array)
        single_tag_match = re.search(r"tags:\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:#|$)", line)
        if single_tag_match:
            tag_name = single_tag_match.group(1)
            violations.append(
                {
                    "type": "tag_naming",
                    "message": "Tags should use square bracket array format",
                    "line": line_num,
                }
            )
            # Also check if the tag is camelCase
            if re.match(r"[A-Z][a-zA-Z]*[A-Z][a-zA-Z]*", tag_name):
                violations.append(
                    {
                        "type": "tag_naming",
                        "message": f'Tag "{tag_name}" should use snake_case',
                        "line": line_num,
                    }
                )

        # Check for camelCase tags in arrays
        tag_array_match = re.search(r"tags:\s*\[(.*)\]", line)
        if tag_array_match:
            tags_content = tag_array_match.group(1)
            # Find unquoted camelCase tags
            camel_tags = re.findall(r"([A-Z][a-zA-Z]*[A-Z][a-zA-Z]*)", tags_content)
            for tag in camel_tags:
                violations.append(
                    {
                        "type": "tag_naming",
                        "message": f'Tag "{tag}" should use snake_case',
                        "line": line_num,
                    }
                )

    return violations


def _check_ansible_way_violations(lines: list[str]) -> list[dict[str, Any]]:
    """Check for violations of The Ansible Way principles.

    Reference: ansible-best-practices-roles-modules skill - ch01
    Principles: Complexity Kills Productivity, Optimize for Readability, Think Declaratively
    """
    violations = []

    for line_num, line in enumerate(lines, 1):
        # Check for procedural shell/command usage that could be declarative
        # Reference: "Think Declaratively" - avoid shell command when modules exist
        if re.search(r'(shell|command):\s*("[^"]*"|\'[^\']*\')', line):
            # Check if it's a simple file operation that could use file/copy/template modules
            shell_content = re.search(r'(shell|command):\s*["\']([^"\']*)["\']', line)
            if shell_content:
                cmd = shell_content.group(2)
                if any(
                    pattern in cmd
                    for pattern in [
                        "echo ",
                        "touch ",
                        "mkdir -p ",
                        "cp ",
                        "mv ",
                        "chmod ",
                        "chown ",
                    ]
                ):
                    violations.append(
                        {
                            "type": "ansible_way",
                            "message": f'Ansible Way: Avoid procedural shell commands when declarative modules exist. Consider using file/copy/template modules instead of: "{cmd[:50]}..."',
                            "line": line_num,
                            "reference": "ansible-best-practices-roles-modules: Think Declaratively",
                        }
                    )

        # Check for overly complex tasks (Complexity Kills Productivity)
        # Look for tasks with too many conditions or nested structures
        if re.search(r"when:\s*\(", line) or " and " in line or " or " in line:
            # Count conditions in when clauses
            when_match = re.search(r"when:\s*([^#]*)", line)
            if when_match:
                when_clause = when_match.group(1)
                if when_clause.count(" and ") > 2 or when_clause.count(" or ") > 2:
                    violations.append(
                        {
                            "type": "ansible_way",
                            "message": f'Ansible Way: Complex when conditions reduce readability. Consider splitting into multiple tasks or using vars. Found {when_clause.count(" and ") + when_clause.count(" or ")} conditions.',
                            "line": line_num,
                            "reference": "ansible-best-practices-roles-modules: Complexity Kills Productivity",
                        }
                    )

        # Check for long lines that reduce readability (Optimize for Readability)
        if len(line) > 120 and not line.strip().startswith("#"):
            violations.append(
                {
                    "type": "ansible_way",
                    "message": f"Ansible Way: Line exceeds 120 characters ({len(line)} chars), reducing readability. Consider breaking into multiple lines.",
                    "line": line_num,
                    "reference": "ansible-best-practices-roles-modules: Optimize for Readability",
                }
            )

        # Check for inline YAML that could be broken out for readability
        if re.search(r":\s*\{.*\}", line) and len(line) > 80:
            violations.append(
                {
                    "type": "ansible_way",
                    "message": "Ansible Way: Complex inline structures reduce readability. Consider using YAML block style or breaking into variables.",
                    "line": line_num,
                    "reference": "ansible-best-practices-roles-modules: Optimize for Readability",
                }
            )

    return violations


def _check_role_design_violations(lines: list[str]) -> list[dict[str, Any]]:
    """Check for violations of Role Design Principles.

    Reference: ansible-best-practices-roles-modules skill - ch02
    Principles: Self-Contained & Focused, Convention over Configuration, Loosely-Coupled
    """
    violations = []

    for line_num, line in enumerate(lines, 1):
        # Check for hard dependencies on other roles (Loosely-Coupled principle)
        # Reference: "Loosely-Coupled - Limit hard dependencies on other roles"
        if re.search(r"-\s*role:", line) or re.search(r"roles:\s*\[", line):
            # Check if role has dependencies that might be too broad
            role_list_match = re.search(r"roles:\s*\[([^\]]*)\]", line)
            if role_list_match:
                role_list = role_list_match.group(1)
                role_count = role_list.count(",") + 1 if role_list.strip() else 0
                if role_count > 3:
                    violations.append(
                        {
                            "type": "role_design",
                            "message": f"Role Design: Role applies {role_count} other roles. Consider splitting into smaller, more focused roles for better loose coupling.",
                            "line": line_num,
                            "reference": "ansible-best-practices-roles-modules: Loosely-Coupled Roles",
                        }
                    )

        # Check for hardcoded values that should be in defaults/vars
        # Look for common patterns like hardcoded paths, ports, usernames
        hardcoded_patterns = [
            (
                r"path:\s*/[^\s#]+",
                "Hardcoded path should be configurable via role defaults",
            ),
            (
                r"port:\s*\d+",
                "Hardcoded port should be configurable via role defaults",
            ),
            (
                r"user:\s*[a-z_]+",
                "Hardcoded username should be configurable via role defaults",
            ),
            (
                r"group:\s*[a-z_]+",
                "Hardcoded group should be configurable via role defaults",
            ),
        ]

        for pattern, message in hardcoded_patterns:
            if re.search(pattern, line) and not re.search(
                r"\{\{", line
            ):  # Skip if it's already templated
                violations.append(
                    {
                        "type": "role_design",
                        "message": f"Role Design: {message} (Convention over Configuration principle).",
                        "line": line_num,
                        "reference": "ansible-best-practices-roles-modules: Convention over Configuration",
                    }
                )

    return violations


def _check_module_design_violations(yaml_content: str, lines: list[str]) -> list[dict[str, Any]]:
    """Check for violations of Module Design Principles.

    Reference: ansible-best-practices-roles-modules skill - ch03
    Principles: User-Centric Abstraction, Idempotency, Fail Fast
    """
    violations = []

    for line_num, line in enumerate(lines, 1):
        # Check for idempotency issues (Idempotency principle)
        # Reference: "Idempotency - Modules must ensure no side-effects occur with multiple runs"

        # Check for modules that are inherently non-idempotent without proper parameters
        non_idempotent_modules = ["command", "shell", "raw"]
        for module in non_idempotent_modules:
            # NOTE: "raw" is iterated but the guard below excludes it, so it
            # can never raise a violation. Preserved as-is; widening the
            # guard would change what this checker reports.
            if (
                module in ("command", "shell")
                and re.search(rf"\b{module}:\s*", line)
                and "creates=" not in line
                and "creates:" not in line
            ):
                violations.append(
                    {
                        "type": "module_design",
                        "message": f'Module Design: "{module}" module is not idempotent by default. Use creates/removes parameters or consider a declarative module.',
                        "line": line_num,
                        "reference": "ansible-best-practices-roles-modules: Idempotency",
                    }
                )

        # Check for User-Centric Abstraction violations
        # Look for low-level implementation details exposed to users
        if re.search(r"url:\s*http[s]?://", line) and not re.search(r"\{\{", line):
            violations.append(
                {
                    "type": "module_design",
                    "message": "Module Design: Hardcoded URLs reduce abstraction. Consider making URLs configurable via variables.",
                    "line": line_num,
                    "reference": "ansible-best-practices-roles-modules: User-Centric Abstraction",
                }
            )

        # Check for check_mode support (Idempotency & Fail Fast)
        if re.search(r"shell:|command:", line):
            # shell and command don't support check_mode well
            violations.append(
                {
                    "type": "module_design",
                    "message": f'Module Design: "{line.split(":")[0]}" module has limited check_mode support. Consider using declarative modules for better check mode behavior.',
                    "line": line_num,
                    "reference": "ansible-best-practices-roles-modules: Check Mode (ch03)",
                }
            )

    # Multi-line analysis for idempotency patterns
    # Check for proper use of state parameters in modules that support it
    stateful_modules = [
        "file",
        "copy",
        "template",
        "package",
        "yum",
        "apt",
        "service",
        "systemd",
    ]
    for line_num, line in enumerate(lines, 1):
        for module in stateful_modules:
            # NOTE: "copy" and "template" are in stateful_modules but absent
            # from the guard, so they never raise a violation. Preserved
            # as-is; adding them would change what this checker reports.
            if (
                module in ("file", "service", "systemd", "package", "yum", "apt")
                and re.search(rf"\b{module}:", line)
                and "state:" not in line
            ):
                violations.append(
                    {
                        "type": "module_design",
                        "message": f'Module Design: "{module}" module should specify state parameter for explicit idempotency control.',
                        "line": line_num,
                        "reference": "ansible-best-practices-roles-modules: Idempotency",
                    }
                )

    return violations


def to_snake_case(camel_str: str) -> str:
    """Convert camelCase to snake_case.

    Args:
        camel_str: String in camelCase format

    Returns:
        String in snake_case format
    """
    # Insert underscore before capital letters that follow lowercase letters
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", camel_str)
    # Insert underscore before capital letters that follow lowercase letters or digits
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
