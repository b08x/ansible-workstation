# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Markdown rendering and on-disk reports for llm_analyzer.

The renderers reproduce the layout the prompt template used to dictate. Moving
it here is the point of the DSPy migration: the signature now returns fields,
and the presentation of those fields is a local formatting decision rather than
something baked into the text sent to the model.

Timestamps here are deliberately *local* time. These strings name and head a
file a person browses; the machine-readable record in :mod:`llm_trace_store`
timestamps in UTC.
"""

from __future__ import absolute_import, division, print_function

import datetime
from pathlib import Path
from typing import Any, Optional

__metaclass__ = type


def render_task_markdown(outputs: dict[str, Any]) -> str:
    """Render task outputs in the layout the prompt template used to dictate."""
    if not outputs:
        return "_No analysis produced._"
    rows = outputs.get("parameters") or []
    param_lines = ["| Parameter | Value | Purpose |", "| :--- | :--- | :--- |"]
    for row in rows:
        if isinstance(row, dict):
            param_lines.append(
                "| {} | {} | {} |".format(
                    row.get("name", ""), row.get("value", ""), row.get("purpose", "")
                )
            )
    fqcn = "Qualified" if outputs.get("is_fqcn") else "Not qualified"
    return "\n".join(
        [
            "### Operational Intent",
            "- **Goal**: {}".format(outputs.get("goal", "")),
            "- **Role**: {}".format(outputs.get("role_in_play", "")),
            "",
            "### Module Signature",
            "- **Module**: {}".format(outputs.get("module", "")),
            f"- **FQCN**: {fqcn}",
            "",
            "### Parameters",
            "\n".join(param_lines),
            "",
            "### Execution Logistics",
            "- **Idempotency**: {} — {}".format(
                outputs.get("idempotency", ""), outputs.get("idempotency_mechanism", "")
            ),
            "- **Change Detection**: {}".format(outputs.get("change_detection", "")),
            "- **Conditions**: {}".format(outputs.get("conditions", "")),
            "- **Delegation**: {}".format(outputs.get("delegation", "")),
            "- **Loop**: {}".format(outputs.get("loop", "")),
            "- **Privilege Escalation**: {}".format(outputs.get("privilege_escalation", "")),
            "- **Error Handling**: {}".format(outputs.get("error_handling", "")),
        ]
    )


def render_play_markdown(outputs: dict[str, Any]) -> str:
    """Render play outputs in the layout the prompt template used to dictate."""
    if not outputs:
        return "_No analysis produced._"
    return "\n".join(
        [
            "### Target Hosts",
            "- **Hosts**: {}".format(outputs.get("hosts", "")),
            "- **Gather Facts**: {}".format("Yes" if outputs.get("gather_facts") else "No"),
            "",
            "### Variable & Role Scoping",
            str(outputs.get("variable_sources", "")),
            "",
            "#### Variable Precedence Risks",
            "- {}".format(outputs.get("precedence_risks", "")),
            "",
            "### Handler Coordination",
            "- **Handlers Defined**: {}".format(outputs.get("handlers_defined", "")),
            "- **Notify Sources**: {}".format(outputs.get("notify_sources", "")),
            "- **Unreachable Handlers**: {}".format(outputs.get("unreachable_handlers", "")),
            "",
            "### Execution Flow",
            "- **Strategy**: {}".format(outputs.get("strategy", "")),
            "- **Roles Applied**: {}".format(outputs.get("roles_applied", "")),
            "- **Sequence**: {}".format(outputs.get("sequence", "")),
            "",
            "### Failure Boundaries",
            "- **Failure Tolerance**: {}".format(outputs.get("failure_tolerance", "")),
            "- **Recovery Patterns**: {}".format(outputs.get("recovery_patterns", "")),
            "- **Error Propagation**: {}".format(outputs.get("error_propagation", "")),
        ]
    )


def render_style_section(style_violations: list[dict[str, Any]]) -> str:
    """Render the style pass as a markdown section, or "" if it found nothing."""
    if not style_violations:
        return ""
    lines = ["", "", "## Style Analysis", ""]
    for violation in style_violations:
        ref = violation.get("reference", "")
        suffix = f" [_Reference: {ref}_]" if ref else ""
        lines.append(
            f"- **Line {violation['line']}** ({violation['type']}): "
            f"{violation['message']}{suffix}"
        )
    return "\n".join(lines) + "\n"


def _report_filename(analysis_type: str, count: int, name: Optional[str]) -> str:
    # Local time on purpose: this names a file a person browses.
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    filename = f"{timestamp}_{analysis_type}_{count}"
    if name:
        # Replace spaces and special characters with underscores
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        filename = f"{filename}_{safe_name}"
    return filename


def save_markdown(
    analysis_dir: Path,
    content: str,
    analysis_type: str,
    name: Optional[str] = None,
    analysis_id: Optional[str] = None,
    count: int = 0,
) -> Path:
    """Save analysis to a markdown file, cross-referenced to its trace row.

    ``count`` is passed in rather than read from a live counter: analyses
    complete out of order on the worker pool, so the counter no longer names
    the analysis in hand by the time this runs.
    """
    filepath = analysis_dir / f"{_report_filename(analysis_type, count, name)}.md"
    with open(filepath, "w") as f:
        f.write(f"# {analysis_type.title()} Analysis\n\n")
        if name:
            f.write(f"**Name:** {name}\n\n")
        f.write(
            "**Timestamp:** "
            # Local time: this header is read by a human, not queried.
            f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"  # noqa: DTZ005
        )
        if analysis_id:
            f.write(f"**Trace:** `{analysis_id}`\n\n")
        f.write("## Analysis\n\n")
        f.write(content)
    return filepath


def save_suggestions(
    analysis_dir: Path,
    suggestions: str,
    analysis_type: str,
    name: Optional[str] = None,
    count: int = 0,
) -> Path:
    """Save structured suggestions for LLM processing."""
    stem = _report_filename(analysis_type, count, name)
    filepath = analysis_dir / f"{stem}_suggestions.dspy"
    with open(filepath, "w") as f:
        f.write(suggestions)
    return filepath
