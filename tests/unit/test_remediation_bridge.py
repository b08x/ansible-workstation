"""The subprocess bridge streams the CLI's progress lines while it runs."""

from __future__ import absolute_import, division, print_function

import json
import sys

from remediation_bridge import PROGRESS_PREFIX, run_cli


def _child(tmp_path, body):
    """A stand-in CLI: a python script run by the real interpreter."""
    script = tmp_path / "cli.py"
    script.write_text("import json, sys, time\n" + body)
    return str(script)


def test_progress_lines_reach_callback_in_order(tmp_path):
    cli = _child(
        tmp_path,
        f"print({PROGRESS_PREFIX!r} + 'diagnosing', file=sys.stderr, flush=True)\n"
        f"print({PROGRESS_PREFIX!r} + 'generating', file=sys.stderr, flush=True)\n"
        "print(json.dumps({'status': 'generated'}))\n",
    )
    seen = []
    outcome = run_cli(
        "diagnose", {}, python=sys.executable, cli_path=cli,
        on_progress=lambda event: seen.append(event["text"]),
    )
    assert seen == ["diagnosing", "generating"]
    assert outcome == {"status": "generated"}


def test_progress_arrives_before_the_child_exits(tmp_path):
    """A line is delivered while the child is still running, not at exit."""
    marker = tmp_path / "released"
    cli = _child(
        tmp_path,
        f"print({PROGRESS_PREFIX!r} + 'started', file=sys.stderr, flush=True)\n"
        f"while not __import__('os').path.exists({str(marker)!r}):\n"
        "    time.sleep(0.02)\n"
        "print(json.dumps({}))\n",
    )

    def on_progress(line):
        # The child blocks until this file exists; if progress were only
        # delivered at exit, the child would never finish.
        marker.write_text(line["text"])

    assert run_cli("diagnose", {}, python=sys.executable, cli_path=cli, on_progress=on_progress) == {}
    assert marker.read_text() == "started"


def test_failure_message_excludes_progress_lines(tmp_path):
    cli = _child(
        tmp_path,
        f"print({PROGRESS_PREFIX!r} + 'diagnosing', file=sys.stderr, flush=True)\n"
        "print('LLM provider openrouter is not usable', file=sys.stderr)\n"
        "sys.exit(3)\n",
    )
    outcome = run_cli("diagnose", {}, python=sys.executable, cli_path=cli, on_progress=lambda _: None)
    assert outcome["failed"] is True
    assert outcome["rc"] == 3
    assert outcome["msg"] == "LLM provider openrouter is not usable"


def test_payload_reaches_child_stdin(tmp_path):
    cli = _child(tmp_path, "print(json.dumps(json.load(sys.stdin)))\n")
    payload = {"diagnostics": {"host": {"ok": True}}, "host": "tinybot"}
    assert run_cli("diagnose", payload, python=sys.executable, cli_path=cli) == payload


def test_missing_interpreter_names_setup(tmp_path):
    outcome = run_cli("diagnose", {}, python=str(tmp_path / "nope"), cli_path=__file__)
    assert outcome["failed"] is True
    assert "bin/setup" in outcome["msg"]


def test_invalid_json_is_reported(tmp_path):
    cli = _child(tmp_path, "print('not json')\n")
    outcome = run_cli("diagnose", {}, python=sys.executable, cli_path=cli)
    assert outcome["failed"] is True
    assert "invalid JSON" in outcome["msg"]


def test_structured_events_are_parsed(tmp_path):
    event = {"event": "done", "text": "drafting", "seconds": 96.4}
    cli = _child(
        tmp_path,
        f"print({PROGRESS_PREFIX!r} + json.dumps({event!r}), file=sys.stderr, flush=True)\n"
        "print(json.dumps({}))\n",
    )
    seen = []
    run_cli("diagnose", {}, python=sys.executable, cli_path=cli, on_progress=seen.append)
    assert seen == [event]
