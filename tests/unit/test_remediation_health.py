"""The pipeline decides from container state, not the model, whether anything is wrong."""

from __future__ import absolute_import, division, print_function

from remediation_health import assess, split_history


def _diag(containers, pods=(), inspect=None, journal=None, host_security=None):
    return {
        "containers": {
            "ok": True,
            "data": {"list": list(containers), "inspect": inspect or {}},
            "error": None,
        },
        "pods": {"ok": True, "data": {"list": list(pods), "inspect": {}}, "error": None},
        "journal": {"ok": True, "data": journal or {}, "error": None},
        "host_security": {"ok": True, "data": host_security or {}, "error": None},
    }


def _c(name, state="running", status="Up 3 minutes"):
    return {"Names": [name], "State": state, "Status": status}


TINYBOT_NOW = [
    _c("ollama"),
    _c("38005075532d-infra"),
    _c("langfuse-postgres", status="Up 3 minutes (healthy)"),
    _c("langfuse-clickhouse", status="Up 3 minutes (healthy)"),
    _c("langfuse-redis", status="Up 3 minutes (healthy)"),
    _c("langfuse-minio", status="Up 3 minutes (healthy)"),
    _c("langfuse-worker"),
    _c("langfuse-web"),
]


def test_all_running_is_healthy():
    health = assess(_diag(TINYBOT_NOW, pods=[{"Name": "langfuse", "Status": "Running"}]))
    assert health["healthy"] is True
    assert health["containers"] == 8
    assert health["running"] == 8
    assert "nothing to remediate" in health["summary"]


def test_exited_container_is_not_healthy():
    containers = [_c("ollama", "exited", "Exited (0) 4 hours ago"), _c("x")]
    health = assess(_diag(containers))
    assert health["healthy"] is False
    assert health["down"] == ["ollama"]


def test_created_but_never_started_is_not_healthy():
    health = assess(_diag([_c("ollama", "created", "Created")]))
    assert health["healthy"] is False
    assert health["down"] == ["ollama"]


def test_unhealthy_healthcheck_is_not_healthy():
    health = assess(_diag([_c("langfuse-web", status="Up 2 minutes (unhealthy)")]))
    assert health["healthy"] is False
    assert health["unhealthy"] == ["langfuse-web"]


def test_degraded_pod_is_not_healthy():
    health = assess(_diag([_c("a")], pods=[{"Name": "langfuse", "Status": "Degraded"}]))
    assert health["healthy"] is False
    assert health["pods_down"] == ["langfuse"]


def test_no_containers_is_not_healthy():
    """A remediation that deleted the container must not read as healthy."""
    health = assess(_diag([]))
    assert health["healthy"] is False
    assert any("no containers" in reason for reason in health["reasons"])


def test_unreadable_container_list_is_not_healthy():
    diagnostics = _diag([])
    diagnostics["containers"] = {"ok": False, "data": None, "error": "podman: not found"}
    health = assess(diagnostics)
    assert health["healthy"] is False
    assert any("podman: not found" in reason for reason in health["reasons"])


def test_selinux_disabled_by_boot_argument_is_warned():
    health = assess(
        _diag(
            TINYBOT_NOW,
            host_security={
                "selinux_mode": "Disabled",
                "selinux_config": "enforcing",
                "kernel_cmdline": "ro quiet selinux=0",
            },
        )
    )
    assert health["healthy"] is True
    assert any("selinux=0" in warning for warning in health["warnings"])


def test_journal_before_latest_start_moves_to_history():
    # 11:29:55 local == 15:29:55 UTC; entries are microseconds since the epoch.
    inspect = {
        "ollama": {
            "ok": True,
            "data": [{"State": {"StartedAt": "2026-09-30T11:29:55.80493123-04:00"}}],
        },
        "old": {"ok": True, "data": [{"State": {"StartedAt": "0001-01-01T00:00:00Z"}}]},
    }
    before = str(int(1790782100 * 1e6))  # 2026-09-30T15:28:20Z, before the start
    after = str(int(1790782300 * 1e6))  # 2026-09-30T15:31:40Z, after the start
    journal = {
        "system": [
            {
                "__REALTIME_TIMESTAMP": before,
                "MESSAGE": "creating /etc/mtab symlink: operation not permitted",
            },
            {"__REALTIME_TIMESTAMP": after, "MESSAGE": "ollama serving"},
        ],
        "user": None,
    }
    result = split_history(_diag(TINYBOT_NOW, inspect=inspect, journal=journal))
    data = result["journal"]["data"]
    assert [e["MESSAGE"] for e in data["system"]] == ["ollama serving"]
    assert [e["MESSAGE"] for e in data["system_history"]] == [
        "creating /etc/mtab symlink: operation not permitted"
    ]
    assert data["user"] is None
    assert result["journal"]["history_before"].startswith("2026-09-30T15:29:55")


def test_split_history_without_start_times_is_unchanged():
    journal = {"system": [{"__REALTIME_TIMESTAMP": "1", "MESSAGE": "x"}]}
    diagnostics = _diag([_c("a")], journal=journal)
    assert split_history(diagnostics)["journal"]["data"] == journal
