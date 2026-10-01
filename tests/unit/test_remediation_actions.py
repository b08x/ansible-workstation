"""fact-3, fact-17: action plugins bridge to the venv CLI and fail safely."""

from __future__ import absolute_import, division, print_function

import io
import json
import subprocess
from types import SimpleNamespace

import pytest

from ansible.plugins.action import ActionBase
from tests.conftest import load_module_file

DIAGNOSE_PATH = "plugins/action/remediation_diagnose.py"
RECORD_PATH = "plugins/action/remediation_record.py"
VERIFY_PATH = "plugins/action/remediation_verify.py"

DIAGNOSE_OUTPUT = {
    "incident_id": "inc-abc123",
    "summary": "langfuse pod degraded",
    "error_signature": "podman:container_state_improper+shm_mount_einval",
    "service": "langfuse",
    "role": "llmops.langfuse",
    "severity": "high",
    "matches": [],
    "status": "generated",
    "playbook_path": "/tmp/pending/inc-abc123.yml",
    "playbook_yaml": "---\n- name: Fix\n  hosts: all\n",
    "rationale": "restart",
    "health_check": {"kind": "http", "target": "http://localhost:3000/api/public/health"},
}


def _action(relative_path, args, check_mode=False):
    plugin_cls = load_module_file(
        "action_" + relative_path.split("/")[-1][:-3], relative_path
    ).ActionModule
    action = plugin_cls.__new__(plugin_cls)
    action._task = SimpleNamespace(args=dict(args))
    action._play_context = SimpleNamespace(check_mode=check_mode)
    return action


def _popen_from(fake_run):
    """Adapt a fake ``subprocess.run`` into the ``Popen`` the bridge uses."""

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            done = fake_run(cmd)
            self.returncode = done.returncode
            self.stdin = io.StringIO()
            self.stdout = io.StringIO(done.stdout)
            self.stderr = io.StringIO(done.stderr)

        def wait(self):
            return self.returncode

    return FakePopen


@pytest.fixture(autouse=True)
def base_run(monkeypatch):
    monkeypatch.setattr(ActionBase, "run", lambda self, tmp=None, task_vars=None: {})


@pytest.fixture
def capture(monkeypatch):
    """Record every module execution and CLI subprocess invocation."""
    state = {"modules": [], "cli": []}

    def fake_execute_module(self, module_name=None, module_args=None, task_vars=None, **kwargs):
        state["modules"].append(module_name)
        return {
            "changed": False,
            "diagnostics": {"host": {"ok": True, "data": {}, "error": None}},
        }

    def fake_run(cmd, input=None, capture_output=True, text=True, env=None, cwd=None):
        state["cli"].append(cmd)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(DIAGNOSE_OUTPUT),
            stderr="",
        )

    monkeypatch.setattr(ActionBase, "_execute_module", fake_execute_module)
    monkeypatch.setattr(subprocess, "Popen", _popen_from(fake_run))
    return state


# fact-3
def test_diagnose_calls_gather_then_cli(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")
    action = _action(DIAGNOSE_PATH, {"pod": "langfuse", "log_lines": 50})
    result = action.run(None, {"inventory_hostname": "tinybot"})

    assert capture["modules"] == ["remediation_gather"]
    assert len(capture["cli"]) == 1
    cmd = capture["cli"][0]
    assert cmd[1].endswith("remediation_cli.py")
    assert cmd[2] == "diagnose"
    assert result["incident_id"] == DIAGNOSE_OUTPUT["incident_id"]
    assert result["changed"] is False
    assert not result.get("failed")


def test_diagnose_gather_args_forwarded(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")

    captured = {}

    def fake_execute_module(self, module_name=None, module_args=None, task_vars=None, **kwargs):
        captured["module_args"] = module_args
        return {"changed": False, "diagnostics": {}}

    monkeypatch.setattr(ActionBase, "_execute_module", fake_execute_module)
    action = _action(DIAGNOSE_PATH, {"pod": "langfuse", "since": "-2h", "extra": "ignored"})
    action.run(None, {"inventory_hostname": "tinybot"})
    assert captured["module_args"] == {"pod": "langfuse", "since": "-2h"}


# fact-17
def test_provider_unreachable_fails_without_changes(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")

    def fake_run(cmd, input=None, capture_output=True, text=True, env=None, cwd=None):
        return subprocess.CompletedProcess(
            cmd,
            3,
            stdout="",
            stderr=(
                "LLM provider openrouter [openrouter/x] is not usable: could "
                "not reach the provider for openrouter"
            ),
        )

    monkeypatch.setattr(subprocess, "Popen", _popen_from(fake_run))
    action = _action(DIAGNOSE_PATH, {})
    result = action.run(None, {"inventory_hostname": "tinybot"})

    assert result["failed"] is True
    assert "provider" in result["msg"]
    assert "could not reach the provider" in result["msg"]
    # Only the read-only gather ran on the host; nothing else was invoked.
    assert capture["modules"] == ["remediation_gather"]
    assert result.get("changed") is False


def test_missing_venv_fails_with_setup_hint(capture, monkeypatch, tmp_path):
    monkeypatch.setenv("REMEDIATION_PYTHON", str(tmp_path / "missing-python"))
    action = _action(DIAGNOSE_PATH, {})
    result = action.run(None, {"inventory_hostname": "tinybot"})
    assert result["failed"] is True
    assert "REMEDIATION_PYTHON" in result["msg"]


def test_check_mode_skips_pipeline(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")
    action = _action(DIAGNOSE_PATH, {}, check_mode=True)
    result = action.run(None, {"inventory_hostname": "tinybot"})
    assert result["skipped"] is True
    assert capture["cli"] == []


def test_record_validates_args(capture):
    action = _action(RECORD_PATH, {"result": "bogus"})
    result = action.run(None, {"inventory_hostname": "tinybot"})
    assert result["failed"] is True
    assert "result" in result["msg"]


def test_record_success_returns_indexed(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")

    def fake_run(cmd, input=None, capture_output=True, text=True, env=None, cwd=None):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"incident_id": "inc-1", "result": "success", "indexed": True}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "Popen", _popen_from(fake_run))
    action = _action(
        RECORD_PATH,
        {
            "incident_id": "inc-1",
            "playbook_path": "/tmp/p.yml",
            "result": "success",
            "confirmed_by": "human",
        },
    )
    result = action.run(None, {"inventory_hostname": "tinybot"})
    assert result["indexed"] is True
    assert result["changed"] is True


def test_verify_returns_resolved(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")

    def fake_run(cmd, input=None, capture_output=True, text=True, env=None, cwd=None):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(
                {
                    "resolved": True,
                    "new_signature": "podman:healthy",
                    "old_signature": "podman:shm_einval",
                    "summary": "all good",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "Popen", _popen_from(fake_run))
    action = _action(
        VERIFY_PATH,
        {"diagnostics": {"host": {}}, "error_signature": "podman:shm_einval"},
    )
    result = action.run(None, {"inventory_hostname": "tinybot"})
    assert result["resolved"] is True
    assert result["changed"] is False


def test_action_plugins_import_only_stdlib_and_ansible():
    import ast

    from tests.conftest import REPO_ROOT

    for path in sorted((REPO_ROOT / "plugins" / "action").glob("remediation_*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                assert not any(n.split(".")[0] in ("dspy", "duckdb") for n in names), path
            if isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                assert root not in ("dspy", "duckdb"), path


def test_diagnose_streams_cli_progress_to_display(capture, monkeypatch):
    """Each stage the CLI reports is displayed under the host's name."""
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")

    def fake_run(cmd, input=None, capture_output=True, text=True, env=None, cwd=None):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps(DIAGNOSE_OUTPUT),
            stderr="REMEDIATION_PROGRESS diagnosing\nREMEDIATION_PROGRESS generating\n",
        )

    monkeypatch.setattr(subprocess, "Popen", _popen_from(fake_run))
    module = load_module_file("action_remediation_diagnose", DIAGNOSE_PATH)
    shown = []
    monkeypatch.setattr(module.display, "display", lambda msg, **kw: shown.append(msg))
    action = module.ActionModule.__new__(module.ActionModule)
    action._task = SimpleNamespace(args={})
    action._play_context = SimpleNamespace(check_mode=False)
    action.run(None, {"inventory_hostname": "tinybot"})
    # The health verdict comes first, then the CLI's stages in order.
    assert shown[0].startswith("tinybot: cannot read the container list")
    assert shown[-2:] == ["tinybot: diagnosing", "tinybot: generating"]


HEALTHY_DIAGNOSTICS = {
    "containers": {
        "ok": True,
        "data": {
            "list": [{"Names": ["ollama"], "State": "running", "Status": "Up"}],
            "inspect": {},
        },
        "error": None,
    },
    "pods": {"ok": True, "data": {"list": [], "inspect": {}}, "error": None},
}


def _healthy_gather(monkeypatch, modules):
    def fake_execute_module(self, module_name=None, module_args=None, task_vars=None, **kwargs):
        modules.append(module_name)
        return {"changed": False, "diagnostics": HEALTHY_DIAGNOSTICS}

    monkeypatch.setattr(ActionBase, "_execute_module", fake_execute_module)


def test_healthy_host_ends_before_any_model_call(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")
    _healthy_gather(monkeypatch, capture["modules"])
    result = _action(DIAGNOSE_PATH, {}).run(None, {"inventory_hostname": "tinybot"})
    assert result["status"] == "healthy"
    assert "nothing to remediate" in result["msg"]
    assert result["changed"] is False
    assert capture["cli"] == []  # no incident, no LLM, no draft


def test_force_diagnoses_a_healthy_host(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")
    _healthy_gather(monkeypatch, capture["modules"])
    result = _action(DIAGNOSE_PATH, {"force": "true"}).run(None, {"inventory_hostname": "tinybot"})
    assert len(capture["cli"]) == 1
    assert result["incident_id"] == DIAGNOSE_OUTPUT["incident_id"]
    assert result["health"]["healthy"] is True


def test_force_is_not_forwarded_to_gather(capture, monkeypatch):
    monkeypatch.setenv("REMEDIATION_PYTHON", "/usr/bin/true")
    seen = {}

    def fake_execute_module(self, module_name=None, module_args=None, task_vars=None, **kwargs):
        seen["args"] = module_args
        return {"changed": False, "diagnostics": HEALTHY_DIAGNOSTICS}

    monkeypatch.setattr(ActionBase, "_execute_module", fake_execute_module)
    _action(DIAGNOSE_PATH, {"force": True, "since": "-2h"}).run(None, {"inventory_hostname": "h"})
    assert seen["args"] == {"since": "-2h"}
