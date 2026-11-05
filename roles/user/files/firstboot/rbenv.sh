#!/bin/sh
# /etc/profile.d/rbenv.sh
# Initialize rbenv shims for all login shells.
# RBENV_ROOT defaults to ~/.rbenv; set explicitly for non-interactive contexts.

export RBENV_ROOT="${RBENV_ROOT:-$HOME/.rbenv}"
if command -v rbenv >/dev/null 2>&1; then
  eval "$(rbenv init -)"
fi
