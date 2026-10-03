# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Render remediation progress events for the terminal.

Standard library only, so the action plugins can import it. On a colour
terminal each event is one styled line in the Charm palette: a host badge, a
state mark (› running, ✓ done, ✗ failed or rejected, ! warning, · info) and the timing
dimmed. Everywhere else (piped output, NO_COLOR, ANSIBLE_NOCOLOR, a screen
reader) the same event is plain ASCII words: ``tinybot: drafting, done in 96s``.
"""

from __future__ import absolute_import, division, print_function

import os

__metaclass__ = type

# Charm palette (lipgloss defaults and the charm.sh brand colours).
PURPLE = (125, 86, 244)  # #7D56F4
GREEN = (4, 181, 117)  # #04B575
PINK = (255, 95, 135)  # #FF5F87
GRAY = (98, 98, 98)  # #626262
YELLOW = (236, 253, 101)  # #ECFD65
WHITE = (250, 250, 250)

RESET = "\x1b[0m"

MARKS = {
    "start": ("›", PURPLE),
    "done": ("✓", GREEN),
    "failed": ("✗", PINK),
    "rejected": ("✗", PINK),
    "warning": ("!", YELLOW),
    "info": ("·", GRAY),
}


def color_enabled(ansible_color, isatty):
    """Colour only on a terminal, with Ansible colour on and NO_COLOR unset."""
    if os.environ.get("NO_COLOR"):
        return False
    return bool(ansible_color and isatty)


def render(host, event, color):
    kind = event.get("event") if event.get("event") in MARKS else "info"
    text = str(event.get("text", ""))
    seconds = event.get("seconds")
    if color:
        return _styled(host, kind, text, seconds)
    return _plain(host, kind, text, seconds)


def _plain(host, kind, text, seconds):
    elapsed = f"{float(seconds):.0f}s" if seconds is not None else ""
    suffix = {
        "start": ", started",
        "done": f", done in {elapsed}" if elapsed else "",
        "failed": f", failed after {elapsed}" if elapsed else ", failed",
    }.get(kind, "")
    if kind in ("rejected", "warning"):
        return f"{host}: {kind}, {text}"
    return f"{host}: {text}{suffix}"


def _styled(host, kind, text, seconds):
    mark, tint = MARKS[kind]
    badge = f"{_bg(PURPLE)}{_fg(WHITE)}\x1b[1m {host} {RESET}"
    body = f"{_fg(PINK)}rejected{RESET} {text}" if kind == "rejected" else text
    if kind == "start":
        tail = f" {_fg(GRAY)}…{RESET}"
    elif seconds is not None and kind in ("done", "failed"):
        tail = f" {_fg(GRAY)}{float(seconds):.0f}s{RESET}"
    else:
        tail = ""
    if kind == "info":
        body = f"{_fg(GRAY)}{body}{RESET}"
    return f"{badge} {_fg(tint)}\x1b[1m{mark}{RESET} {body}{tail}"


def _fg(rgb):
    return "\x1b[38;2;{};{};{}m".format(*rgb)


def _bg(rgb):
    return "\x1b[48;2;{};{};{}m".format(*rgb)
