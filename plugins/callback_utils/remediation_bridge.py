# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Subprocess bridge from the remediation action plugins to the venv CLI.

Standard library only: this module is imported inside the ``ansible-playbook``
process, which cannot import dspy or duckdb. It runs
``remediation_cli.py <subcommand>`` in the ``.venv`` interpreter, writes the
payload as JSON on the child's stdin and parses one JSON document from its
stdout.

The child reports progress on stderr, one JSON event per line, prefixed with
``PROGRESS_PREFIX``: ``{"event": "start|done|failed|rejected|info", "text":
..., "seconds": ...}``. Each event is handed to ``on_progress`` as a dict the
moment it arrives, so a multi-minute diagnosis is visible while it runs. Every
other stderr line is kept as the failure message.
"""

from __future__ import absolute_import, division, print_function

import json
import os
import subprocess
import threading

__metaclass__ = type

PROGRESS_PREFIX = "REMEDIATION_PROGRESS "

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI_PATH = os.path.join(REPO_ROOT, "plugins", "callback_utils", "remediation_cli.py")


def default_python():
    """The venv interpreter, overridable with REMEDIATION_PYTHON."""
    return os.environ.get("REMEDIATION_PYTHON") or os.path.join(
        REPO_ROOT, ".venv", "bin", "python"
    )


def _event(raw):
    try:
        event = json.loads(raw)
    except ValueError:
        event = None
    if not isinstance(event, dict):
        event = {"event": "info", "text": raw}
    return event


def run_cli(subcommand, payload, python=None, cli_path=CLI_PATH, on_progress=None):
    """Run one CLI subcommand. Returns its JSON outcome or a failed result."""
    python = python or default_python()
    if not os.path.isfile(python):
        return {
            "failed": True,
            "msg": (
                f"remediation venv interpreter not found at {python}; "
                "run bin/setup or set REMEDIATION_PYTHON"
            ),
        }
    if not os.path.isfile(cli_path):
        return {"failed": True, "msg": f"remediation CLI not found at {cli_path}"}
    try:
        proc = subprocess.Popen(
            [python, cli_path, subcommand],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
            cwd=REPO_ROOT,
        )
    except OSError as e:
        return {"failed": True, "msg": f"cannot run {python}: {e}"}

    # stdin and stdout each get a thread so a large payload or a large result
    # cannot fill a pipe buffer while this thread is reading stderr.
    stdout_chunks = []

    def feed():
        try:
            proc.stdin.write(json.dumps(payload))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def drain():
        stdout_chunks.append(proc.stdout.read())

    workers = [threading.Thread(target=feed), threading.Thread(target=drain)]
    for worker in workers:
        worker.start()

    errors = []
    for line in proc.stderr:
        line = line.rstrip("\n")
        if line.startswith(PROGRESS_PREFIX):
            if on_progress is not None:
                on_progress(_event(line[len(PROGRESS_PREFIX):]))
        elif line.strip():
            errors.append(line)
    returncode = proc.wait()
    for worker in workers:
        worker.join()
    stdout = "".join(stdout_chunks)

    if returncode != 0:
        return {
            "failed": True,
            "rc": returncode,
            "msg": "\n".join(errors).strip()
            or f"remediation_cli {subcommand} exited {returncode}",
        }
    try:
        return json.loads(stdout)
    except ValueError:
        return {
            "failed": True,
            "msg": f"remediation_cli {subcommand} wrote invalid JSON: {stdout[:300]}",
        }
