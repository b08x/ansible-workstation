"""fact-4, fact-8: DSPy signatures parse and the prompt carries the matches."""

from __future__ import absolute_import, division, print_function

import json

import dspy
from dspy.utils import DummyLM
from remediation_signatures import (
    PLAYBOOK_SKELETON,
    SIGNATURE_VERSION,
    build,
    trim_diagnostics,
)

DIAGNOSE_ANSWER = {
    "summary": "The langfuse pod is degraded: the web container reports an "
    "improper state because its shm tmpfs mount fails with EINVAL.",
    "error_signature": "podman:container_state_improper+shm_mount_einval",
    "service": "langfuse",
    "role": "llmops.langfuse",
    "severity": "high",
}

GENERATE_ANSWER = {
    "playbook_yaml": (
        "---\n"
        "- name: Recreate the langfuse pod without the stale shm mount\n"
        "  hosts: all\n"
        "  tasks:\n"
        "    - name: Restart the pod\n"
        "      ansible.builtin.command:\n"
        "        cmd: podman pod restart langfuse\n"
        "      changed_when: true\n"
    ),
    "rationale": "Restarting the pod remounts the shm tmpfs.",
    "health_check": {
        "kind": "http",
        "target": "http://localhost:3000/api/public/health",
    },
}


class RecordingLM(DummyLM):
    """DummyLM that records every prompt it is asked."""

    def __init__(self, answers):
        super().__init__(answers)
        self.prompts = []

    def forward(self, prompt=None, messages=None, **kwargs):
        self.prompts.append(messages or [{"role": "user", "content": prompt}])
        return super().forward(prompt=prompt, messages=messages, **kwargs)


def _text(prompts):
    return "\n".join(m["content"] for m in prompts[-1])


# fact-4
def test_diagnose_output_fields_parse():
    diagnose_sig, _ = build()
    lm = DummyLM(answers=[DIAGNOSE_ANSWER])
    with dspy.context(lm=lm):
        prediction = dspy.Predict(diagnose_sig)(diagnostics_json="{}")
    assert prediction.summary == DIAGNOSE_ANSWER["summary"]
    assert prediction.error_signature == DIAGNOSE_ANSWER["error_signature"]
    assert prediction.service == "langfuse"
    assert prediction.role == "llmops.langfuse"
    assert prediction.severity in ("low", "medium", "high", "critical")
    assert "tinybot" not in prediction.error_signature


def test_generate_output_fields_parse():
    _, generate_sig = build()
    lm = DummyLM(answers=[GENERATE_ANSWER])
    with dspy.context(lm=lm):
        prediction = dspy.Predict(generate_sig)(
            summary="s",
            diagnostics_json="{}",
            similar_incidents="[]",
            role_context="none",
            playbook_skeleton=PLAYBOOK_SKELETON,
        )
    assert prediction.playbook_yaml.startswith("---")
    assert prediction.rationale
    health = prediction.health_check
    assert health.kind == "http"
    assert health.target == "http://localhost:3000/api/public/health"


def test_signature_version_recorded():
    assert isinstance(SIGNATURE_VERSION, str)


def test_skeleton_reaches_the_prompt():
    _, generate_sig = build()
    lm = RecordingLM(answers=[GENERATE_ANSWER])
    with dspy.context(lm=lm):
        dspy.Predict(generate_sig)(
            summary="s",
            diagnostics_json="{}",
            similar_incidents="[]",
            role_context="none",
            playbook_skeleton=PLAYBOOK_SKELETON,
        )
    prompt = _text(lm.prompts)
    assert "playbook_skeleton" in prompt
    assert "hosts: all" in prompt


# fact-8
def test_similar_incidents_reach_the_prompt_when_present():
    _, generate_sig = build()
    lm = RecordingLM(answers=[GENERATE_ANSWER])
    similar = [
        {
            "incident_id": "inc-previous",
            "summary": "same shm einval",
            "playbook_yaml": "# SEEN_BEFORE_MARKER playbook",
        }
    ]
    with dspy.context(lm=lm):
        dspy.Predict(generate_sig)(
            summary="s",
            diagnostics_json="{}",
            similar_incidents=json.dumps(similar),
            role_context="none",
            playbook_skeleton=PLAYBOOK_SKELETON,
        )
    assert "SEEN_BEFORE_MARKER" in _text(lm.prompts)


def test_empty_similar_incidents_reach_the_prompt():
    _, generate_sig = build()
    lm = RecordingLM(answers=[GENERATE_ANSWER])
    with dspy.context(lm=lm):
        dspy.Predict(generate_sig)(
            summary="s",
            diagnostics_json="{}",
            similar_incidents="[]",
            role_context="none",
            playbook_skeleton=PLAYBOOK_SKELETON,
        )
    prompt = _text(lm.prompts)
    assert "similar_incidents" in prompt
    assert "SEEN_BEFORE_MARKER" not in prompt


def test_trim_diagnostics_prefers_failing_containers():
    diagnostics = {
        "host": {
            "ok": True,
            "data": {
                "os_release": {"NAME": "Fedora"},
                "meminfo": {"MemTotal": "1", "MemFree": "1", "HugePages_Total": "0"},
                "disk": "\n".join(f"line{i}" for i in range(20)),
            },
            "error": None,
        },
        "pods": {
            "ok": True,
            "data": {
                "list": [
                    {"Name": "langfuse", "Status": "Degraded"},
                    {"Name": "healthy", "Status": "Running"},
                ],
                "inspect": {"langfuse": {"x": 1}, "healthy": {"x": 2}},
            },
            "error": None,
        },
        "containers": {
            "ok": True,
            "data": {
                "list": [
                    {"Names": ["langfuse-web"], "State": "exited"},
                    {"Names": ["side"], "State": "running"},
                ],
                "inspect": {"langfuse-web": {"a": 1}, "side": {"b": 2}},
            },
            "error": None,
        },
        "logs": {
            "ok": True,
            "data": {"langfuse-web": {"ok": True, "data": "line\n" * 5, "error": None}},
            "error": None,
        },
        "journal": {
            "ok": True,
            "data": {
                "user": [
                    {"PRIORITY": "3", "MESSAGE": "conmon: error shm EINVAL"},
                    {"PRIORITY": "6", "MESSAGE": "hello world"},
                ]
            },
            "error": None,
        },
        "mounts": {"ok": True, "data": [{"target": "/dev/shm"}], "error": None},
        "selinux": {"ok": False, "data": None, "error": "ausearch unavailable"},
    }
    trimmed = trim_diagnostics(diagnostics, char_budget=8000)
    pods = trimmed["pods"]["data"]
    assert [p["Name"] for p in pods["list"]] == ["langfuse"]
    assert "healthy" not in pods["inspect"]
    containers = trimmed["containers"]["data"]
    assert [c["Names"][0] for c in containers["list"]] == ["langfuse-web"]
    assert "side" not in containers["inspect"]
    journal = trimmed["journal"]["data"]["user"]
    assert journal == [
        {
            "__REALTIME_TIMESTAMP": None,
            "PRIORITY": "3",
            "_SYSTEMD_UNIT": None,
            "MESSAGE": "conmon: error shm EINVAL",
        }
    ]
    assert trimmed["host"]["data"]["meminfo"] == {"MemTotal": "1", "MemFree": "1"}
    assert len(trimmed["host"]["data"]["disk"]) <= 6


def test_trim_diagnostics_drops_sections_over_budget():
    diagnostics = {
        "host": {"ok": True, "data": {"big": "x" * 5000}, "error": None},
        "mounts": {
            "ok": True,
            "data": [{"target": "/dev/shm/" + "y" * 400, "source": "z" * 200}],
            "error": None,
        },
        "pods": {"ok": True, "data": {"list": []}, "error": None},
    }
    trimmed = trim_diagnostics(diagnostics, char_budget=5100)
    assert trimmed["host"]["ok"] is True
    # The mounts section did not fit and is marked omitted, not silently
    # truncated.
    assert trimmed["mounts"]["error"] == "omitted: context budget exceeded"
