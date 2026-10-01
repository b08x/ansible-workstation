"""fact-10, fact-12, fact-13, fact-15: the orchestrating playbook's gates.

These run ``playbooks/remediate.yml`` against implicit localhost with the
venv CLI replaced by a stub that logs every subcommand, and ``ansible-playbook``
shimmed in PATH so the "run the approved playbook" task is observable. The
LLM, Ollama and DuckDB are never touched.
"""

from __future__ import absolute_import, division, print_function

import http.server
import json
import os
import stat
import subprocess
import threading
from pathlib import Path

import yaml

from tests.conftest import REPO_ROOT

ANSIBLE_PLAYBOOK = REPO_ROOT / ".venv" / "bin" / "ansible-playbook"
PLAYBOOK = REPO_ROOT / "playbooks" / "remediate.yml"

STUB_CLI = """\
#!/usr/bin/env python3
import json, os, sys

sub = sys.argv[2]
try:
    payload = json.load(sys.stdin)
except Exception:
    payload = {}

with open(os.environ["REMEDIATION_STUB_LOG"], "a") as fh:
    fh.write(json.dumps({"sub": sub, "payload": payload}) + "\\n")

if sub == "diagnose":
    print(json.dumps({
        "incident_id": "inc-stub001",
        "summary": "langfuse pod degraded container state improper shm einval",
        "error_signature": "podman:container_state_improper+shm_mount_einval",
        "service": "langfuse",
        "role": "llmops.langfuse",
        "severity": "high",
        "matches": [],
        "status": "generated",
        "rationale": "stub",
        "health_check": {
            "kind": os.environ.get("REMEDIATION_HEALTH_KIND", "http"),
            "target": os.environ.get("REMEDIATION_HEALTH_TARGET", "http://127.0.0.1:9/"),
        },
        "playbook_path": "/tmp/stub-pending.yml",
        "playbook_yaml": "---\\n- name: Stub\\n  hosts: all\\n  tasks: []\\n",
    }))
elif sub == "verify":
    resolved = os.environ.get("REMEDIATION_VERIFY_RESOLVED", "true") == "true"
    new_sig = "podman:healthy" if resolved else "podman:container_state_improper+shm_mount_einval"
    print(json.dumps({
        "resolved": resolved,
        "new_signature": new_sig,
        "old_signature": payload.get("error_signature"),
        "summary": "stub",
    }))
elif sub == "record":
    result = payload.get("result")
    print(json.dumps({
        "incident_id": payload.get("incident_id"),
        "result": result,
        "indexed": result == "success",
    }))
"""

ANSIBLE_PLAYBOOK_SHIM = """\
#!/bin/sh
echo "{\\"sub\\": \\"ansible-playbook-run\\", \\"payload\\": {\\"argv\\": \\"$@\\", \\"roles_path\\": \\"$ANSIBLE_ROLES_PATH\\"}}" >> "$REMEDIATION_STUB_LOG"
exit 0
"""


def _write_executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _run(tmp_path, extra_args=(), env_overrides=None):
    stub = tmp_path / "stub-cli"
    _write_executable(stub, STUB_CLI)
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir(exist_ok=True)
    _write_executable(shim_dir / "ansible-playbook", ANSIBLE_PLAYBOOK_SHIM)
    log = tmp_path / "stub.log"
    log.write_text("")

    env = os.environ.copy()
    env["REMEDIATION_PYTHON"] = str(stub)
    env["REMEDIATION_STUB_LOG"] = str(log)
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env.update(env_overrides or {})

    proc = subprocess.run(
        [
            str(ANSIBLE_PLAYBOOK),
            str(PLAYBOOK),
            "-e",
            "target=localhost",
            # The real gather runs on this workstation; its containers must
            # not decide whether these gate tests reach the model stage.
            "-e",
            "remediation_force=true",
            *extra_args,
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return proc, _read_log(log), proc.stdout + proc.stderr


def _subs(entries):
    return [e["sub"] for e in entries]


def _record_entry(entries):
    for entry in entries:
        if entry["sub"] == "record":
            return entry["payload"]
    return None


def test_playbook_exists_with_required_gates():
    document = yaml.safe_load(PLAYBOOK.read_text())
    tasks = document[0]["tasks"]
    reserved = {
        "name",
        "when",
        "register",
        "vars",
        "tags",
        "ignore_errors",
        "failed_when",
        "changed_when",
        "delegate_to",
        "become",
        "args",
    }
    modules = [next(key for key in task if key not in reserved) for task in tasks]
    assert "remediation_diagnose" in modules
    assert "ansible.builtin.pause" in modules
    assert "ansible.builtin.fail" in modules
    assert "remediation_gather" in modules
    assert "remediation_verify" in modules
    assert "remediation_record" in modules
    order = {}
    for i, module in enumerate(modules):
        order.setdefault(module, i)
    assert (
        order["remediation_diagnose"]
        < order["ansible.builtin.pause"]
        < order["ansible.builtin.command"]
        < order["remediation_gather"]
        < order["remediation_verify"]
        < order["remediation_record"]
    )


def test_unapproved_run_stops_before_execution(tmp_path):
    proc, entries, output = _run(tmp_path)
    assert proc.returncode != 0, "run without approval must fail, not complete"
    assert "diagnose" in _subs(entries)
    # fact-10: nothing was executed on the host.
    assert "ansible-playbook-run" not in _subs(entries)
    assert "record" not in _subs(entries)
    assert "not approved" in output or "Abort" in output


def test_approved_run_executes_and_records_success(tmp_path):
    server = http.server.HTTPServer(
        ("127.0.0.1", 0),
        lambda *a, **kw: type(
            "H",
            (http.server.BaseHTTPRequestHandler,),
            {
                "do_GET": lambda self: (
                    self.send_response(200),
                    self.end_headers(),
                    self.wfile.write(b"ok"),
                ),
                "log_message": lambda self, *a: None,
            },
        )(*a, **kw),
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        proc, entries, output = _run(
            tmp_path,
            extra_args=("-e", "remediation_approve=yes", "-e", "remediation_confirm=yes"),
            env_overrides={"REMEDIATION_HEALTH_TARGET": f"http://127.0.0.1:{port}/"},
        )
    finally:
        server.shutdown()
    assert proc.returncode == 0, output
    subs = _subs(entries)
    assert "diagnose" in subs
    assert "ansible-playbook-run" in subs
    # The approved playbook lives outside the repo; the run must point the
    # child ansible-playbook at the repo roles explicitly.
    run_entry = next(e for e in entries if e["sub"] == "ansible-playbook-run")
    assert run_entry["payload"]["roles_path"].endswith("/roles")
    assert "verify" in subs
    assert "record" in subs
    record = _record_entry(entries)
    assert record["result"] == "success"


def test_unresolved_signature_records_failed(tmp_path):
    proc, entries, output = _run(
        tmp_path,
        extra_args=("-e", "remediation_approve=yes", "-e", "remediation_confirm=yes"),
        env_overrides={"REMEDIATION_VERIFY_RESOLVED": "false"},
    )
    record = _record_entry(entries)
    assert record is not None
    assert record["result"] == "failed"


def test_unconfirmed_records_unconfirmed(tmp_path):
    proc, entries, output = _run(
        tmp_path,
        extra_args=("-e", "remediation_approve=yes"),
    )
    record = _record_entry(entries)
    assert record is not None
    assert record["result"] == "unconfirmed"


def test_healthy_host_ends_before_the_gates():
    document = yaml.safe_load(PLAYBOOK.read_text())
    tasks = document[0]["tasks"]
    names = [task["name"] for task in tasks]
    end = next(t for t in tasks if t.get("ansible.builtin.meta") == "end_host")
    assert "healthy" in end["when"] and "ansible_check_mode" in end["when"]
    assert tasks[0]["remediation_diagnose"]["force"].startswith("{{ remediation_force")
    first_pause = next(i for i, t in enumerate(tasks) if "ansible.builtin.pause" in t)
    assert names.index(end["name"]) < first_pause


def test_check_mode_run_ends_cleanly(tmp_path):
    proc, entries, output = _run(tmp_path, extra_args=("--check",))
    assert proc.returncode == 0, output
    subs = _subs(entries)
    assert "diagnose" not in subs  # check mode never reaches the CLI
    assert "ansible-playbook-run" not in subs
