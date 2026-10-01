# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Diagnose action plugin: gather on the host, pipeline on the controller.

Runs the read-only ``remediation_gather`` module on the target host, then
hands the diagnostics to ``remediation_cli.py diagnose`` in the ``.venv``
interpreter via a subprocess bridge. The action plugin itself imports only
the standard library and Ansible; dspy and duckdb live on the child's side.

The language model never executes anything. This plugin returns a generated,
guard-checked playbook; ``playbooks/remediate.yml`` runs it only after human
approval.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

from ansible.module_utils.parsing.convert_bool import boolean
from ansible.utils.color import ANSIBLE_COLOR
from ansible.utils.display import Display

from ansible.plugins.action import ActionBase

__metaclass__ = type

# The bridge lives in ../callback_utils, beside the CLI it runs; the plugin
# loader would treat a helper placed in this directory as an action plugin.
_UTILS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "callback_utils"
)
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

import remediation_bridge  # noqa: E402
import remediation_health  # noqa: E402
import remediation_style  # noqa: E402

display = Display()

GATHER_ARGS = ("pod", "log_lines", "journal_units", "since")


class ActionModule(ActionBase):

    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        self._supports_check_mode = True
        result = super().run(tmp, task_vars)
        del tmp
        if task_vars is None:
            task_vars = {}

        module_args = {key: value for key, value in self._task.args.items() if key in GATHER_ARGS}
        gather = self._execute_module(
            module_name="remediation_gather",
            module_args=module_args,
            task_vars=task_vars,
        )
        if gather.get("failed"):
            return gather

        # Decide from container state, not the model, whether anything is
        # wrong. A healthy host ends here: no incident, no model call.
        health = remediation_health.assess(gather.get("diagnostics") or {})
        self._show(task_vars, "done" if health["healthy"] else "info", health["summary"])
        for warning in health["warnings"]:
            self._show(task_vars, "warning", warning)
        force = boolean(self._task.args.get("force", False), strict=False)
        if health["healthy"] and not force:
            result.update(
                changed=False,
                status="healthy",
                health=health,
                msg=health["summary"],
            )
            return result

        if self._play_context.check_mode:
            result.update(
                changed=False,
                skipped=True,
                msg="check mode: read-only diagnostics gathered; "
                "LLM pipeline skipped because it writes the incident store",
            )
            return result

        payload = {
            "diagnostics": gather.get("diagnostics"),
            "host": task_vars.get("inventory_hostname"),
        }
        outcome = self._cli("diagnose", payload, task_vars)
        if outcome.get("failed"):
            result.update(changed=False, **outcome)
            return result

        result.update(outcome)
        result["health"] = health
        result["changed"] = False
        return result

    def _show(self, task_vars, event, text):
        host = (task_vars or {}).get("inventory_hostname") or "localhost"
        color = remediation_style.color_enabled(ANSIBLE_COLOR, sys.stdout.isatty())
        display.display(remediation_style.render(host, {"event": event, "text": text}, color))

    def _cli(self, subcommand, payload, task_vars=None):
        """Run the venv CLI, echoing each stage it reports as it happens."""
        host = (task_vars or {}).get("inventory_hostname") or "localhost"
        color = remediation_style.color_enabled(ANSIBLE_COLOR, sys.stdout.isatty())
        return remediation_bridge.run_cli(
            subcommand,
            payload,
            on_progress=lambda event: display.display(remediation_style.render(host, event, color)),
        )
