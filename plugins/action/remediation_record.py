# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Record action plugin: write a remediation outcome, index on success.

Runs after the human confirmation gate in ``playbooks/remediate.yml``. A
``success`` outcome copies the playbook into the index directory so semantic
search can offer it for future incidents; ``failed`` and ``unconfirmed``
outcomes are recorded but never indexed.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

from ansible.plugins.action import ActionBase
from ansible.utils.color import ANSIBLE_COLOR
from ansible.utils.display import Display

__metaclass__ = type

# The bridge lives in ../callback_utils, beside the CLI it runs; the plugin
# loader would treat a helper placed in this directory as an action plugin.
_UTILS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "callback_utils"
)
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

import remediation_bridge  # noqa: E402
import remediation_style  # noqa: E402

display = Display()


RESULT_VALUES = ("success", "failed", "unconfirmed")


class ActionModule(ActionBase):

    _supports_check_mode = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        del tmp

        args = self._task.args
        incident_id = args.get("incident_id")
        playbook_path = args.get("playbook_path")
        outcome_result = args.get("result")
        if not incident_id or not playbook_path or outcome_result not in RESULT_VALUES:
            result["failed"] = True
            result["msg"] = (
                f"remediation_record requires incident_id, playbook_path and "
                f"result in {RESULT_VALUES}; got result={outcome_result!r}"
            )
            return result

        payload = {
            "incident_id": incident_id,
            "playbook_path": playbook_path,
            "result": outcome_result,
            "confirmed_by": args.get("confirmed_by"),
        }
        outcome = self._cli("record", payload, task_vars)
        if outcome.get("failed"):
            result.update(**outcome)
            return result

        result.update(outcome)
        result["changed"] = True
        return result

    def _cli(self, subcommand, payload, task_vars=None):
        """Run the venv CLI, echoing each stage it reports as it happens."""
        host = (task_vars or {}).get("inventory_hostname") or "localhost"
        color = remediation_style.color_enabled(ANSIBLE_COLOR, sys.stdout.isatty())
        return remediation_bridge.run_cli(
            subcommand,
            payload,
            on_progress=lambda event: display.display(
                remediation_style.render(host, event, color)
            ),
        )
