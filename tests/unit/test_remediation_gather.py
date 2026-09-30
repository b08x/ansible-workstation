"""fact-1, fact-2: the gather module is read-only and returns every section."""

from __future__ import absolute_import, division, print_function

import json

import pytest
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes

from tests.conftest import load_module_file

MODULE_PATH = "plugins/modules/remediation_gather.py"

CANNED = {
    ("uname", "-r"): (0, "6.14.4-200.fc41.x86_64", ""),
    ("df", "-h"): (0, "Filesystem Size Used\n/dev/sda1 100G 50G", ""),
    ("podman", "version", "--format", "json"): (
        0,
        json.dumps({"Version": "5.2.3", "APIVersion": "5.2.3"}),
        "",
    ),
    ("podman", "pod", "ps", "--format", "json"): (
        0,
        json.dumps([{"Name": "langfuse", "Status": "Degraded", "Created": "2024"}]),
        "",
    ),
    ("podman", "pod", "inspect", "langfuse"): (
        0,
        json.dumps({"Name": "langfuse", "State": "Degraded", "Containers": []}),
        "",
    ),
    ("podman", "ps", "-a", "--format", "json"): (
        0,
        json.dumps(
            [
                {
                    "Names": ["langfuse-web"],
                    "Id": "abc123",
                    "State": "exited",
                    "Pod": "langfuse",
                }
            ]
        ),
        "",
    ),
    ("podman", "inspect", "abc123"): (
        0,
        json.dumps(
            [
                {
                    "Name": "langfuse-web",
                    "Config": {
                        "Env": [
                            "POSTGRES_PASSWORD=hunter2",
                            "PATH=/usr/bin",
                            "DATABASE_URL=postgresql://langfuse:urlpw1@postgres:5432/langfuse",
                        ]
                    },
                }
            ]
        ),
        "",
    ),
    ("podman", "logs", "--tail", "200", "langfuse-web"): (
        0,
        "level=error msg=\"container state improper: shm mount EINVAL\"\n"
        "connecting to postgresql://langfuse:logpw2@localhost:5432/langfuse\n"
        "env NEXTAUTH_SECRET=logsecret3 loaded\n",
        "",
    ),
    ("findmnt", "-J"): (
        0,
        json.dumps(
            {
                "filesystems": [
                    {"target": "/dev/shm", "source": "tmpfs", "fstype": "tmpfs"},
                    {"target": "/home", "source": "/dev/sda1", "fstype": "ext4"},
                ]
            }
        ),
        "",
    ),
    ("getenforce",): (0, "Disabled\n", ""),
    ("last", "-x", "-n", "6", "reboot", "shutdown"): (
        0,
        "reboot   system boot  6.12.0-211.56.1. Wed Sep 30 07:50   still running\n"
        "shutdown system down  6.12.0-211.56.1. Wed Sep 30 07:50 - 07:50  (00:00)\n",
        "",
    ),
    ("loginctl", "show-user", "tester", "-p", "Linger", "--value"): (0, "no\n", ""),
    ("ausearch", "-m", "AVC", "-ts", "recent"): (
        1,
        "",
        "ausearch: command not found",
    ),
}

JOURNAL_LINES = [
    {"__REALTIME_TIMESTAMP": "1", "PRIORITY": "3", "MESSAGE": "conmon: error binding shm"},
    {"__REALTIME_TIMESTAMP": "2", "PRIORITY": "3", "MESSAGE": "redis://:journalpw4@redis:6379 refused"},
]


class AnsibleExitJson(Exception):
    pass


class AnsibleFailJson(Exception):
    pass


def _exit_json(*args, **kwargs):
    kwargs["failed"] = False
    raise AnsibleExitJson(kwargs)


def _fail_json(*args, **kwargs):
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


def _set_module_args(args):
    if isinstance(args, dict):
        args = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(args)


KERNEL_LOG = (
    "2026-09-30T07:52:54-04:00 tinybot kernel: tmpfs: Unknown parameter 'context'\n"
    "2026-09-30T07:52:55-04:00 tinybot kernel: usb 1-1: new high-speed USB device\n"
)


def _fake_run_command(self, args, **kwargs):
    if args[0] == "journalctl" and "-k" in args:
        return 0, KERNEL_LOG, ""
    if args[0] == "journalctl":
        if "--user" in args:
            return 0, "\n".join(json.dumps(e) for e in JOURNAL_LINES), ""
        return 0, "", ""
    key = tuple(args)
    if key not in CANNED:
        return 1, "", f"unexpected command: {args}"
    return CANNED[key]


@pytest.fixture
def facts_gather(monkeypatch):
    monkeypatch.setenv("USER", "tester")
    monkeypatch.setenv("LOGNAME", "tester")
    monkeypatch.setattr(basic.AnsibleModule, "run_command", _fake_run_command)
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", _exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", _fail_json)
    return load_module_file("remediation_gather", MODULE_PATH)


def _run(gather_module, args=None):
    _set_module_args(args or {})
    with pytest.raises(AnsibleExitJson) as excinfo:
        gather_module.main()
    return excinfo.value.args[0]


def test_returns_every_section(facts_gather):
    result = _run(facts_gather)
    diagnostics = result["diagnostics"]
    assert set(diagnostics) == {
        "host",
        "pods",
        "containers",
        "logs",
        "journal",
        "mounts",
        "selinux",
        "host_security",
    }
    host = diagnostics["host"]["data"]
    assert host["os_release"]["PRETTY_NAME"] or "NAME" in host["os_release"]
    assert host["kernel"]
    assert host["podman_version"]["Version"] == "5.2.3"
    assert "MemTotal" in host["meminfo"]
    assert host["disk"]
    assert host["hostname"]
    assert diagnostics["pods"]["data"]["list"][0]["Name"] == "langfuse"
    assert diagnostics["pods"]["data"]["inspect"]["langfuse"]["data"]["State"] == "Degraded"
    assert diagnostics["containers"]["data"]["list"][0]["State"] == "exited"
    assert "langfuse-web" in diagnostics["containers"]["data"]["inspect"]
    assert "container state improper" in diagnostics["logs"]["data"]["langfuse-web"]["data"]
    assert diagnostics["journal"]["data"]["user"][0]["MESSAGE"]
    targets = [m["target"] for m in diagnostics["mounts"]["data"]]
    assert "/dev/shm" in targets
    assert "/home" not in targets


def test_changed_false_and_check_mode_safe(facts_gather):
    result = _run(facts_gather, {"_ansible_check_mode": True})
    assert result["changed"] is False
    assert result["failed"] is False


def test_secrets_redacted_before_leaving_host(facts_gather):
    result = _run(facts_gather)
    inspects = result["diagnostics"]["containers"]["data"]["inspect"]
    blob = json.dumps(inspects)
    assert "hunter2" not in blob
    assert "POSTGRES_PASSWORD=REDACTED" in blob


def test_secret_values_redacted_in_every_section(facts_gather):
    """Credentials hide in values, not only under secret-looking keys."""
    diagnostics = _run(facts_gather)["diagnostics"]
    blob = json.dumps(diagnostics)
    for secret in ("urlpw1", "logpw2", "logsecret3", "journalpw4"):
        assert secret not in blob, secret
    assert "postgresql://langfuse:REDACTED@postgres:5432/langfuse" in blob
    assert "redis://:REDACTED@redis:6379" in blob
    assert "NEXTAUTH_SECRET=REDACTED" in blob


def test_redaction_keeps_diagnostic_text(facts_gather):
    diagnostics = _run(facts_gather)["diagnostics"]
    blob = json.dumps(diagnostics)
    assert "PATH=/usr/bin" in blob
    assert "container state improper: shm mount EINVAL" in blob
    assert "conmon: error binding shm" in blob


@pytest.mark.parametrize(
    "text",
    [
        "https://example.com/health",
        "http://localhost:3000/api/public/health",
        "authentication failed for user langfuse",
    ],
)
def test_redaction_leaves_non_secrets_alone(facts_gather, text):
    assert facts_gather.redact(text) == text


def test_selinux_section_degrades_with_reason(facts_gather):
    result = _run(facts_gather)
    selinux = result["diagnostics"]["selinux"]
    assert selinux["ok"] is False
    assert "ausearch" in selinux["error"]


def test_pod_filter_selects_pod(facts_gather):
    result = _run(facts_gather, {"pod": "langfuse"})
    pods = result["diagnostics"]["pods"]["data"]["list"]
    assert [p["Name"] for p in pods] == ["langfuse"]


def test_host_security_section(facts_gather):
    """The host-level evidence behind the 2026-09-30 tinybot incident."""
    security = _run(facts_gather)["diagnostics"]["host_security"]
    assert security["ok"] is True
    data = security["data"]
    assert data["selinux_mode"] == "Disabled"
    assert data["linger"] == "no"
    assert any("Unknown parameter 'context'" in line for line in data["kernel_log"])
    assert not any("USB" in line for line in data["kernel_log"])
    assert data["boots"][0].startswith("reboot")
    # Read from the real host running the test; present or reported, never missing.
    for field in ("kernel_cmdline", "lsm", "selinux_config"):
        assert field in data or f"{field}_error" in data


def test_host_security_tolerates_missing_tools(facts_gather, monkeypatch):
    def no_tools(self, args, **kwargs):
        if args[0] in ("getenforce", "last", "loginctl") or (args[0] == "journalctl" and "-k" in args):
            return 127, "", f"{args[0]}: command not found"
        return _fake_run_command(self, args, **kwargs)

    monkeypatch.setattr(basic.AnsibleModule, "run_command", no_tools)
    security = _run(facts_gather)["diagnostics"]["host_security"]
    assert security["ok"] is True
    assert "getenforce" in security["error"]
