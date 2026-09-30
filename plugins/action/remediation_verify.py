# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Verify action plugin: is the original error signature gone?

Runs the diagnosis signature once more against freshly gathered read-only
diagnostics and compares the error signature. A remediation only counts as
successful when the new signature differs from the original one; the
orchestrating playbook additionally requires the generated health check to
pass and a human to confirm.
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



class ActionModule(ActionBase):

    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        self._supports_check_mode = True
        result = super().run(tmp, task_vars)
        del tmp

        args = self._task.args
        diagnostics = args.get("diagnostics")
        error_signature = args.get("error_signature")
        if not isinstance(diagnostics, dict) or not error_signature:
            result["failed"] = True
            result["msg"] = (
                "remediation_verify requires 'diagnostics' (the registered "
                "output of a remediation_gather task) and 'error_signature'"
            )
            return result

        if self._play_context.check_mode:
            result.update(
                changed=False,
                skipped=True,
                msg="check mode: LLM verification skipped",
            )
            return result

        payload = {
            "diagnostics": diagnostics,
            "error_signature": error_signature,
        }
        outcome = self._cli("verify", payload, task_vars)
        if outcome.get("failed"):
            result.update(changed=False, **outcome)
            return result

        result.update(outcome)
        result["changed"] = False
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
