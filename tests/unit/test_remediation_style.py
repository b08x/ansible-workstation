"""Progress events render styled on a terminal and as plain words elsewhere."""

from __future__ import absolute_import, division, print_function

import re

import pytest
from remediation_style import color_enabled, render

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

EVENTS = [
    ({"event": "start", "text": "drafting"}, "tinybot: drafting, started"),
    ({"event": "done", "text": "drafting", "seconds": 96.4}, "tinybot: drafting, done in 96s"),
    ({"event": "failed", "text": "drafting", "seconds": 3}, "tinybot: drafting, failed after 3s"),
    (
        {"event": "rejected", "text": "volume guard: podman rm -v"},
        "tinybot: rejected, volume guard: podman rm -v",
    ),
    ({"event": "info", "text": "2 similar past incidents"}, "tinybot: 2 similar past incidents"),
    ({"event": "warning", "text": "SELinux is disabled"}, "tinybot: warning, SELinux is disabled"),
]


@pytest.mark.parametrize("event,plain", EVENTS, ids=[e[0]["event"] for e in EVENTS])
def test_plain_mode_is_words_only(event, plain):
    line = render("tinybot", event, color=False)
    assert line == plain
    assert not ANSI_RE.search(line)
    # Nothing for a screen reader to announce but the words themselves.
    assert not re.search(r"[^\x20-\x7e]", line)


@pytest.mark.parametrize("event,plain", EVENTS, ids=[e[0]["event"] for e in EVENTS])
def test_color_mode_carries_the_same_words(event, plain):
    line = render("tinybot", event, color=True)
    assert ANSI_RE.search(line)
    visible = ANSI_RE.sub("", line)
    assert "tinybot" in visible
    assert event["text"] in visible


def test_color_mode_marks_each_state():
    marks = {e["event"]: ANSI_RE.sub("", render("h", e, color=True)).split()[1] for e, _ in EVENTS}
    assert marks["start"] == "›"
    assert marks["done"] == "✓"
    assert marks["failed"] == "✗"
    assert marks["rejected"] == "✗"
    assert marks["warning"] == "!"


def test_unknown_event_renders_as_info():
    assert render("h", {"text": "x"}, color=False) == "h: x"


def test_no_color_env_disables_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled(ansible_color=True, isatty=True) is False


def test_color_needs_a_terminal_and_ansible_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(ansible_color=True, isatty=True) is True
    assert color_enabled(ansible_color=True, isatty=False) is False
    assert color_enabled(ansible_color=False, isatty=True) is False
