# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Turn style violations into concrete, actionable edits.

Split from :mod:`llm_style` on purpose. Detection answers "what is wrong here"
and is cheap and deterministic; repair answers "what should it say instead" and
is a pile of per-violation-type heuristics that grows every time a checker is
added. Keeping them apart means a new checker does not force a new fix, and a
better fix does not risk changing what gets reported.

The emitted format is DSPy's structured-output envelope, hand-written. See
``docs/pdca/001-llm-analyzer-dspy.md`` -- this is a known rough edge, kept
verbatim through the module split rather than reworked here.
"""

from __future__ import absolute_import, division, print_function

import json
import re
from typing import Any, Optional

from llm_style import analyze_style, to_snake_case

__metaclass__ = type


def generate_structured_suggestions(yaml_content: str, file_path: str = "ansible_file.yml") -> str:
    """Generate structured suggestions for LLM processing in DSPy format.

    Args:
        yaml_content: The YAML content to analyze
        file_path: Path to the file being analyzed

    Returns:
        Structured output with DSPy field markers and JSON suggestions
    """
    violations = analyze_style(yaml_content)
    suggestions = []

    for violation in violations:
        suggestion = _violation_to_suggestion(violation, yaml_content)
        if suggestion:
            suggestions.append(suggestion)

    # Format in DSPy structured output format
    output_parts = [
        "[[ ## file_path ## ]]",
        file_path,
        "",
        "[[ ## suggestions ## ]]",
        json.dumps(suggestions, indent=2),
        "",
        "[[ ## completed ## ]]",
    ]

    return "\n".join(output_parts)


def _violation_to_suggestion(
    violation: dict[str, Any], yaml_content: str
) -> Optional[dict[str, Any]]:
    """Convert a style violation to an actionable suggestion."""
    lines = yaml_content.split("\n")
    if violation["line"] <= 0 or violation["line"] > len(lines):
        return None

    line_content = lines[violation["line"] - 1]

    suggestion = {
        "type": "replace",
        "line_number": violation["line"],
        "violation_type": violation["type"],
        "reason": violation["message"],
    }

    # Generate specific fixes based on violation type
    if violation["type"] == "variable_naming":
        suggestion.update(_generate_variable_naming_fix(line_content, violation))
    elif violation["type"] == "tag_naming":
        suggestion.update(_generate_tag_naming_fix(line_content, violation))
    elif violation["type"] == "task_structure":
        suggestion.update(_generate_task_structure_fix(line_content, violation))
    elif violation["type"] == "ansible_way":
        suggestion.update(_generate_ansible_way_fix(line_content, violation))
    elif violation["type"] == "role_design":
        suggestion.update(_generate_role_design_fix(line_content, violation))
    elif violation["type"] == "module_design":
        suggestion.update(_generate_module_design_fix(line_content, violation))

    return suggestion


def _generate_variable_naming_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for variable naming violations."""
    old_text = line_content.strip()
    new_text = old_text

    # Fix camelCase variables in Jinja templates
    if "snake_case" in violation["message"]:
        camel_pattern = r"{{\s*([a-z][a-zA-Z]*[A-Z][a-zA-Z]*)\s*}}"
        match = re.search(camel_pattern, old_text)
        if match:
            camel_var = match.group(1)
            snake_var = to_snake_case(camel_var)
            new_text = old_text.replace(f"{{{{ {camel_var} }}}}", f"{{{{ {snake_var} }}}}")

    # Fix variables in vars sections
    elif "role prefix" in violation["message"]:
        var_pattern = r"^(\s*)([A-Z][a-zA-Z]*)\s*:"
        match = re.match(var_pattern, old_text)
        if match:
            indent, var_name = match.groups()
            snake_var = to_snake_case(var_name)
            new_text = f"{indent}role_{snake_var}:"

    return {"old_text": old_text, "new_text": new_text}


def _generate_tag_naming_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for tag naming violations."""
    old_text = line_content.strip()
    new_text = old_text

    # Fix single string/unquoted tags to array format
    if "array format" in violation["message"]:
        if "tags:" in old_text:
            # Extract tag value
            tag_match = re.search(r"tags:\s*([^\s#]+)", old_text)
            if tag_match:
                tag_value = tag_match.group(1).strip("\"'")
                # Convert to snake_case if needed
                if re.match(r"[A-Z][a-zA-Z]*[A-Z][a-zA-Z]*", tag_value):
                    tag_value = to_snake_case(tag_value)
                new_text = re.sub(r"tags:\s*[^\s#]+", f'tags: ["{tag_value}"]', old_text)

    # Fix camelCase tags in arrays
    elif "snake_case" in violation["message"]:
        camel_tags = re.findall(r"([A-Z][a-zA-Z]*[A-Z][a-zA-Z]*)", old_text)
        for camel_tag in camel_tags:
            snake_tag = to_snake_case(camel_tag)
            new_text = new_text.replace(camel_tag, f'"{snake_tag}"')

    return {"old_text": old_text, "new_text": new_text}


def _generate_task_structure_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for task structure violations."""
    return {
        "old_text": line_content.strip(),
        "new_text": "# TODO: Reorder task attributes - name, module, become, loop, when, tags, notify",
        "note": "Task attribute reordering requires multi-line changes. Manual intervention recommended.",
    }


def _generate_ansible_way_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for Ansible Way principle violations."""
    msg = violation.get("message", "")
    old_text = line_content.strip()

    # Shell/command task that should use a declarative module
    shell_match = re.search(r"(shell|command):\s*[\"\']([^\"\']*)[\"\']", old_text)
    if shell_match:
        cmd = shell_match.group(2)
        module_map = {
            "mkdir -p": "file: path=... state=directory",
            "touch": "file: path=... state=touch",
            "chmod": "file: path=... mode=...",
            "chown": "file: path=... owner=... group=...",
            "cp": "copy: src=... dest=...",
            "mv": "command: creates=... removes=...",
            "echo": "copy/lineinfile/template",
        }
        suggested_module = "declarative module"
        for pattern, module in module_map.items():
            if pattern in cmd:
                suggested_module = module
                break
        return {
            "old_text": old_text,
            "new_text": f"# TODO: Replace shell/command with {suggested_module}",
            "note": f"Shell command '{cmd[:60]}' should use a declarative Ansible module for idempotency.",
        }

    # Long line or complex inline structure
    if "120 characters" in msg or "inline structures" in msg:
        return {
            "old_text": old_text,
            "new_text": "# TODO: Break this line into YAML block style or extract into variables",
            "note": "Complex inline YAML reduces readability. Use block style or variable extraction.",
        }

    # Complex when conditions
    if "when conditions" in msg:
        return {
            "old_text": old_text,
            "new_text": "# TODO: Split complex when clause into multiple tasks or use vars",
            "note": "Complex when conditions reduce readability. Consider splitting into separate tasks.",
        }

    # Generic fallback
    return {
        "old_text": old_text,
        "new_text": f"# TODO: Ansible Way - {msg[:80]}",
        "note": "Refer to ansible-best-practices-roles-modules skill for guidance.",
    }


def _generate_role_design_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for Role Design principle violations."""
    msg = violation.get("message", "")
    old_text = line_content.strip()

    # Hardcoded values that should be configurable
    if "Hardcoded" in msg and "Convention over Configuration" in msg:
        # Extract the hardcoded value pattern
        value_match = re.search(r"(path|port|user|group):\s*(\S+)", old_text)
        if value_match:
            key, value = value_match.groups()
            var_name = f"{{{{ {key} }}}}"
            return {
                "old_text": old_text,
                "new_text": re.sub(rf"{key}:\s*\S+", f"{key}: {var_name}", old_text),
                "note": f"Move '{value}' to role defaults/ for Convention over Configuration.",
            }

    # Too many roles applied
    if "Role applies" in msg and "Loosely-Coupled" in msg:
        return {
            "old_text": old_text,
            "new_text": "# TODO: Split into smaller, focused roles for loose coupling",
            "note": "One role = one service. Consider splitting for reuse and portability.",
        }

    # Generic fallback
    return {
        "old_text": old_text,
        "new_text": f"# TODO: Role Design - {msg[:80]}",
        "note": "Refer to ansible-best-practices-roles-modules ch02 for guidance.",
    }


def _generate_module_design_fix(line_content: str, violation: dict[str, Any]) -> dict[str, str]:
    """Generate fix for Module Design principle violations."""
    msg = violation.get("message", "")
    old_text = line_content.strip()

    # command/shell without creates/removes
    if "not idempotent by default" in msg and ("command" in msg or "shell" in msg):
        module_match = re.search(r"(command|shell):\s*", old_text)
        if module_match:
            return {
                "old_text": old_text,
                "new_text": f"{old_text}  # TODO: Add creates/removes parameter for idempotency",
                "note": "Add creates= or removes= to make shell/command tasks idempotent.",
            }

    # Stateful module missing state parameter
    if "should specify state parameter" in msg:
        module_match = re.search(r"(\w+):\s*", old_text)
        if module_match:
            module_name = module_match.group(1)
            return {
                "old_text": old_text,
                "new_text": f"{old_text}\n    state: present  # TODO: Set explicit state for idempotency",
                "note": f"'{module_name}' module should declare state: present/absent/started/stopped explicitly.",
            }

    # Hardcoded URLs
    if "Hardcoded URLs" in msg:
        url_match = re.search(r"url:\s*(https?://\S+)", old_text)
        if url_match:
            url = url_match.group(1)
            return {
                "old_text": old_text,
                "new_text": re.sub(
                    rf"url:\s*{re.escape(url)}", "url: {{ download_url }}", old_text
                ),
                "note": f"Move URL '{url[:50]}' to role defaults/ for User-Centric Abstraction.",
            }

    # Limited check_mode support
    if "check_mode" in msg and "limited" in msg:
        return {
            "old_text": old_text,
            "new_text": "# TODO: Replace shell/command with declarative module for check_mode support",
            "note": "shell/command modules don't support --check well. Use declarative alternatives.",
        }

    # Generic fallback
    return {
        "old_text": old_text,
        "new_text": f"# TODO: Module Design - {msg[:80]}",
        "note": "Refer to ansible-best-practices-roles-modules ch03 for guidance.",
    }
