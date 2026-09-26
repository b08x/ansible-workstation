# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""DSPy signatures for Ansible task and play analysis.

These replace the hand-built f-string templates that previously encoded the
output format inside the prompt. The distinction matters for the goal of
optimising later: a ``Signature`` is an addressable object an optimiser can
rewrite the instructions of, whereas a string literal is not.

``SIGNATURE_VERSION`` is recorded on every stored trace. Without it, rows
produced by two different revisions of these signatures pool together and any
before/after comparison is noise.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

SIGNATURE_VERSION = "1.0.0"


def build():
    """Construct the signature classes.

    Deferred into a function so that importing this module does not import
    ``dspy``. The callback is loaded on every ``ansible-playbook`` invocation,
    including runs where analysis is disabled; ``import dspy`` pulls in litellm
    and pydantic and costs seconds.
    """
    from typing import Literal

    import dspy
    from pydantic import BaseModel, Field

    class TaskParameter(BaseModel):
        name: str = Field(description="Parameter name as written in the task")
        value: str = Field(description="Value as written, templates left verbatim")
        purpose: str = Field(description="Factual description of the parameter's effect")

    class AnalyzeAnsibleTask(dspy.Signature):
        """Document an Ansible task as a non-evaluative systems auditor.

        Report factual descriptions only. Observed problems with idempotency,
        style, or security may be stated as factual observations. Do not
        prescribe rewrites.
        """

        task_yaml: str = dspy.InputField(desc="The Ansible task, as YAML")
        style_observations: str = dspy.InputField(
            desc="Style-checker findings for this task; incorporate where relevant. "
            "May be empty."
        )

        goal: str = dspy.OutputField(
            desc="One sentence describing the target state this task enforces"
        )
        role_in_play: str = dspy.OutputField(
            desc="The task's function within the wider playbook sequence"
        )
        module: str = dspy.OutputField(desc="Module name, FQCN where one is used")
        is_fqcn: bool = dspy.OutputField(desc="True if the module is fully qualified")
        parameters: list[TaskParameter] = dspy.OutputField(
            desc="Every parameter passed to the module"
        )
        idempotency: Literal["explicit", "implicit", "not_handled"] = dspy.OutputField(
            desc="explicit: handled via creates/removes/changed_when. "
            "implicit: the module is inherently idempotent. "
            "not_handled: repeated runs may cause side effects."
        )
        idempotency_mechanism: str = dspy.OutputField(
            desc="How idempotency is achieved, or why it is not"
        )
        change_detection: str = dspy.OutputField(desc="register/changed_when usage, or 'Default'")
        conditions: str = dspy.OutputField(desc="when conditionals, or 'None'")
        delegation: str = dspy.OutputField(desc="delegate_to value, or 'None'")
        loop: str = dspy.OutputField(desc="loop/with_items usage, or 'None'")
        privilege_escalation: str = dspy.OutputField(desc="become user/group details, or 'None'")
        error_handling: str = dspy.OutputField(
            desc="ignore_errors/rescue/failed_when behaviour, or 'None'"
        )

    class AnalyzeAnsiblePlay(dspy.Signature):
        """Document an Ansible play as a non-evaluative systems auditor.

        Report factual descriptions only. Do not prescribe rewrites.
        """

        play_yaml: str = dspy.InputField(desc="The Ansible play, as YAML")
        style_observations: str = dspy.InputField(
            desc="Style-checker findings for this play. May be empty."
        )

        hosts: str = dspy.OutputField(desc="The hosts pattern")
        gather_facts: bool = dspy.OutputField(desc="Whether facts are gathered")
        variable_sources: str = dspy.OutputField(
            desc="Markdown table: Source | Key | Value or Notes"
        )
        precedence_risks: str = dspy.OutputField(
            desc="Variable names likely to conflict across scopes, or " "'None observed'"
        )
        handlers_defined: str = dspy.OutputField(desc="Handler names, or 'None'")
        notify_sources: str = dspy.OutputField(desc="Which tasks notify which handlers")
        unreachable_handlers: str = dspy.OutputField(
            desc="Handlers notified only in unreachable paths, or 'None'"
        )
        strategy: str = dspy.OutputField(desc="linear / free / serial batching")
        roles_applied: str = dspy.OutputField(desc="Roles in order, or 'None'")
        sequence: str = dspy.OutputField(
            desc="Chronological summary of pre_tasks, roles, tasks, post_tasks"
        )
        failure_tolerance: str = dspy.OutputField(
            desc="max_fail_percentage / any_errors_fatal, or 'Default'"
        )
        recovery_patterns: str = dspy.OutputField(desc="block/rescue/always usage, or 'None'")
        error_propagation: str = dspy.OutputField(desc="ignore_errors locations, or 'None'")

    return AnalyzeAnsibleTask, AnalyzeAnsiblePlay


def build_judge():
    """Signature for scoring the prose fields the structural metric cannot see.

    ``goal``, ``role_in_play`` and ``idempotency_mechanism`` carry the analysis's
    actual value-add and none of them are checkable against the YAML. This judge
    covers them. Its scores are written to a separate ``judgments`` source so
    they can be compared against the free structural score rather than blended
    into it -- if the two disagree, that disagreement is the finding.
    """
    from typing import Literal

    import dspy

    class JudgeTaskAnalysis(dspy.Signature):
        """Rate how well an analysis describes the Ansible task it was given.

        Judge only groundedness and informativeness of the prose. Do not reward
        length, hedging, or restating the YAML verbatim.
        """

        task_yaml: str = dspy.InputField(desc="The task that was analysed")
        goal: str = dspy.InputField(desc="The analysis's stated goal")
        role_in_play: str = dspy.InputField(desc="The analysis's stated role")
        idempotency_mechanism: str = dspy.InputField(desc="The analysis's idempotency explanation")

        grounded: Literal["yes", "partly", "no"] = dspy.OutputField(
            desc="yes if every claim is supported by the task YAML"
        )
        informative: Literal["yes", "partly", "no"] = dspy.OutputField(
            desc="yes if it says more than the YAML alone shows"
        )
        score: float = dspy.OutputField(desc="Overall quality from 0.0 to 1.0")
        rationale: str = dspy.OutputField(desc="One sentence justifying the score")

    return JudgeTaskAnalysis
