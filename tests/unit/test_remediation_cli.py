"""fact-4, 5, 7, 8, 9, 11, 12, 13, 17 exercised through the CLI bridge."""

from __future__ import absolute_import, division, print_function

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import remediation_cli
import remediation_store
from dspy.utils import DummyLM
from remediation_cli import (
    EXIT_OLLAMA,
    EXIT_USAGE,
    cmd_diagnose,
    cmd_record,
    cmd_verify,
)
from remediation_store import RemediationStore

from tests.conftest import StubEmbedder

DIAGNOSE_ANSWER = {
    "summary": "langfuse pod degraded container state improper shm tmpfs mount einval",
    "error_signature": "podman:container_state_improper+shm_mount_einval",
    "service": "langfuse",
    "role": "llmops.langfuse",
    "severity": "high",
}

BENIGN_PLAYBOOK = (
    "---\n"
    "- name: Recreate the langfuse pod\n"
    "  hosts: all\n"
    "  tasks:\n"
    "    - name: Restart the pod\n"
    "      ansible.builtin.command:\n"
    "        cmd: podman pod restart langfuse\n"
    "      changed_when: true\n"
)

VOLUME_REMOVING_PLAYBOOK = BENIGN_PLAYBOOK.replace(
    "podman pod restart langfuse", "podman volume rm langfuse_pgdata"
)

GENERATE_ANSWER = {
    "playbook_yaml": BENIGN_PLAYBOOK,
    "rationale": "Restart remounts the shm tmpfs.",
    "health_check": {"kind": "http", "target": "http://localhost:3000/api/public/health"},
}


class RecordingLM(DummyLM):
    def __init__(self, answers):
        super().__init__(answers)
        self.prompts = []

    def forward(self, prompt=None, messages=None, **kwargs):
        self.prompts.append(messages or [{"role": "user", "content": prompt}])
        return super().forward(prompt=prompt, messages=messages, **kwargs)


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Isolated CLI run: temp store, stub embedder, passing guard tools."""
    store_root = tmp_path / "store"
    monkeypatch.setattr(remediation_cli, "DEFAULT_STORE", store_root)
    monkeypatch.setattr(remediation_store, "OllamaEmbedder", StubEmbedder)
    monkeypatch.setenv("REMEDIATION_ANSIBLE_PLAYBOOK", "/usr/bin/true")
    monkeypatch.setenv("REMEDIATION_ANSIBLE_LINT", "/usr/bin/true")
    return store_root


@pytest.fixture
def fake_analyzer(monkeypatch):
    """Patch _analyzer() to return a fake analyzer wrapping the given LM."""

    def _make(lm):
        analyzer = SimpleNamespace(lm=lm, provider="test-provider", model_string="test/model")
        monkeypatch.setattr(remediation_cli, "_analyzer", lambda: analyzer)
        return lm

    return _make


def _diagnose(monkeypatch):
    """Patch _analyzer() with a RecordingLM serving canned answers."""
    lm = RecordingLM(answers=[DIAGNOSE_ANSWER, GENERATE_ANSWER])
    monkeypatch.setattr(
        remediation_cli,
        "_analyzer",
        lambda: SimpleNamespace(lm=lm, provider="test-provider", model_string="test/model"),
    )
    return lm


def test_diagnose_generates_pending_playbook(cli_env, monkeypatch, capsys):
    _diagnose(monkeypatch)
    rc = cmd_diagnose(
        {"diagnostics": {"host": {"ok": True, "data": {}, "error": None}}, "host": "tinybot"}
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "generated"
    assert out["tier"] == "llm"
    assert out["template_version"] is None
    assert out["error_signature"] == DIAGNOSE_ANSWER["error_signature"]
    assert out["service"] == "langfuse"
    assert out["severity"] == "high"
    assert out["playbook_yaml"] == BENIGN_PLAYBOOK.strip()
    pending = Path(out["playbook_path"])
    assert pending.parent == cli_env / "playbooks" / "pending"
    assert pending.is_file()
    # fact-5: the incident landed in the JSONL source of truth.
    records = (cli_env / "incidents.jsonl").read_text().splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["incident_id"] == out["incident_id"]


def test_diagnose_known_signature_uses_template_tier(cli_env, monkeypatch, capsys):
    """A known error signature never consults the model for generation.

    The recording LM serves only the diagnosis answer; a second (generation)
    call would exhaust its answers and fail the test.
    """
    lm = RecordingLM(
        answers=[
            dict(
                DIAGNOSE_ANSWER,
                error_signature="podman:pod_state_exited",
                role="langfuse",
            )
        ]
    )
    monkeypatch.setattr(
        remediation_cli,
        "_analyzer",
        lambda: SimpleNamespace(lm=lm, provider="test-provider", model_string="test/model"),
    )
    rc = cmd_diagnose({"diagnostics": {}, "host": "tinybot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "generated"
    assert out["tier"] == "template"
    assert out["template_id"] == "langfuse_pod_exited"
    assert len(lm.prompts) == 1, "template tier must not call the generator"
    assert "langfuse_force_recreate" in out["playbook_yaml"]
    assert out["health_check"]["kind"] == "http"
    pending = Path(out["playbook_path"])
    assert pending.is_file()
    assert "langfuse_force_recreate" in pending.read_text()


def test_diagnose_rejects_volume_removing_playbook(cli_env, monkeypatch, capsys):
    lm = RecordingLM(
        answers=[
            DIAGNOSE_ANSWER,
            dict(GENERATE_ANSWER, playbook_yaml=VOLUME_REMOVING_PLAYBOOK),
        ]
    )
    monkeypatch.setattr(
        remediation_cli,
        "_analyzer",
        lambda: SimpleNamespace(lm=lm, provider="test-provider", model_string="test/model"),
    )
    rc = cmd_diagnose({"diagnostics": {}, "host": "tinybot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    assert any("volume" in reason for reason in out["rejected_reasons"])
    rejected = Path(out["playbook_path"])
    assert rejected.parent == cli_env / "playbooks" / "rejected"
    assert rejected.is_file()
    assert not list((cli_env / "playbooks" / "pending").iterdir())


def test_diagnose_syntax_check_failure_rejects(cli_env, monkeypatch, capsys):
    monkeypatch.setenv("REMEDIATION_ANSIBLE_PLAYBOOK", "/usr/bin/false")
    _diagnose(monkeypatch)
    rc = cmd_diagnose({"diagnostics": {}, "host": "tinybot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    assert any("syntax-check" in r for r in out["rejected_reasons"])


def test_diagnose_lint_failure_rejects(cli_env, monkeypatch, capsys):
    monkeypatch.setenv("REMEDIATION_ANSIBLE_LINT", "/usr/bin/false")
    _diagnose(monkeypatch)
    rc = cmd_diagnose({"diagnostics": {}, "host": "tinybot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    assert any("ansible-lint" in r for r in out["rejected_reasons"])


def _seed_promoted_incident(cli_env):
    store = RemediationStore(cli_env, StubEmbedder())
    incident_id = store.record_incident(
        host="tinybot",
        summary=DIAGNOSE_ANSWER["summary"],
        error_signature="podman:container_state_improper+shm_mount_einval",
        service="langfuse",
        role="llmops.langfuse",
        severity="high",
    )
    pending = store.pending_dir / f"{incident_id}.yml"
    pending.write_text(BENIGN_PLAYBOOK.replace("hosts: all", "# INDEX_MARKER\nhosts: all"))
    store.record_outcome(incident_id=incident_id, playbook_path=str(pending), result="success")
    return incident_id


def test_diagnose_matches_feed_generation_context(cli_env, monkeypatch, capsys):
    incident_id = _seed_promoted_incident(cli_env)
    lm = _diagnose(monkeypatch)
    rc = cmd_diagnose({"diagnostics": {}, "host": "soundbot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["matches"], "a similar promoted incident must be found"
    top = out["matches"][0]
    assert top["incident_id"] == incident_id
    assert top["remediation_playbook"]
    generation_prompt = "\n".join(m["content"] for m in lm.prompts[-1])
    assert "INDEX_MARKER" in generation_prompt


def test_diagnose_without_matches_omits_context(cli_env, monkeypatch, capsys):
    lm = _diagnose(monkeypatch)
    rc = cmd_diagnose({"diagnostics": {}, "host": "soundbot"})
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["matches"] == []
    generation_prompt = "\n".join(m["content"] for m in lm.prompts[-1])
    assert "INDEX_MARKER" not in generation_prompt


def test_diagnose_ollama_unreachable_fails_named(cli_env, monkeypatch, capsys):
    class DeadOllamaEmbedder:
        model = "embeddinggemma:latest"

        def __init__(self, host=None, model="embeddinggemma:latest", timeout=0.0):
            pass

        def embed(self, texts):
            raise remediation_store.RemediationError(
                "Ollama embedding service unreachable at http://127.0.0.1:9 "
                "(model embeddinggemma:latest): connection refused"
            )

    monkeypatch.setattr(remediation_store, "OllamaEmbedder", DeadOllamaEmbedder)
    _diagnose(monkeypatch)
    rc = cmd_diagnose({"diagnostics": {}, "host": "tinybot"})
    assert rc == EXIT_OLLAMA
    err = capsys.readouterr().err
    assert "Ollama" in err


def test_verify_resolved_and_unresolved(cli_env, monkeypatch, capsys):
    signature = "podman:container_state_improper+shm_mount_einval"
    for new_signature, resolved in ((signature, False), ("podman:healthy", True)):
        lm = RecordingLM(answers=[dict(DIAGNOSE_ANSWER, error_signature=new_signature)])
        monkeypatch.setattr(
            remediation_cli,
            "_analyzer",
            lambda: SimpleNamespace(lm=lm, provider="test-provider", model_string="test/model"),
        )
        rc = cmd_verify({"diagnostics": {}, "error_signature": signature})
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["resolved"] is resolved
        assert out["new_signature"] == new_signature


def test_record_success_indexes_playbook(cli_env, capsys):
    store = RemediationStore(cli_env, StubEmbedder())
    incident_id = store.record_incident(
        host="tinybot",
        summary="s",
        error_signature="podman:shm_einval",
        service="langfuse",
        role="llmops.langfuse",
        severity="high",
    )
    pending = store.pending_dir / f"{incident_id}.yml"
    pending.write_text(BENIGN_PLAYBOOK)
    rc = cmd_record(
        {
            "incident_id": incident_id,
            "playbook_path": str(pending),
            "result": "success",
            "confirmed_by": "human",
        }
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["indexed"] is True
    assert (cli_env / "index" / f"{incident_id}.yml").read_text() == BENIGN_PLAYBOOK


def test_record_unconfirmed_not_indexed(cli_env, capsys):
    store = RemediationStore(cli_env, StubEmbedder())
    incident_id = store.record_incident(
        host="tinybot",
        summary="s",
        error_signature="podman:shm_einval",
        service="langfuse",
        role="llmops.langfuse",
        severity="high",
    )
    pending = store.pending_dir / f"{incident_id}.yml"
    pending.write_text(BENIGN_PLAYBOOK)
    rc = cmd_record(
        {
            "incident_id": incident_id,
            "playbook_path": str(pending),
            "result": "unconfirmed",
        }
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["indexed"] is False
    assert not list((cli_env / "index").iterdir())


def test_record_invalid_result_fails(cli_env, capsys):
    rc = cmd_record({"incident_id": "x", "playbook_path": "y", "result": "bogus"})
    assert rc == EXIT_USAGE


def test_diagnose_requires_diagnostics(cli_env, capsys):
    rc = cmd_diagnose({})
    assert rc == EXIT_USAGE
