#!/usr/bin/env bash
# /etc/profile.d/syncopated-firstboot.sh: trigger stage 1 of
# syncopated-firstboot on local console login.
# Runs on interactive login shells on /dev/tty1 for regular users while the
# machine-level pull marker is absent (the marker is world-readable so no
# sudo is needed on the hot path).
# shellcheck disable=SC2317

# Exit if non-interactive shell
[[ $- == *i* ]] || return 0 2>/dev/null || exit 0

# Exit if SSH session
if [[ -n "${SSH_CONNECTION:-}" ]] || [[ -n "${SSH_TTY:-}" ]] || [[ -n "${SSH_CLIENT:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi

# Exit if root user
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  return 0 2>/dev/null || exit 0
fi

# Trigger only on tty1
if [[ $(tty 2>/dev/null) != "/dev/tty1" ]]; then
  return 0 2>/dev/null || exit 0
fi

# Exit if the machine pull marker already exists: the workstation ansible
# pull wrote it after full convergence, and stage 1 has nothing left to do.
# The marker lives in the primary user's home (world-readable 0644, written
# root:root), so a plain test -f is enough — no sudo on the login hot path and
# nothing under /root, which non-root users cannot stat on stock installs (/root is 0550).
_machine_marker_home="${HOME:-/home/$(id -un)}"
_machine_marker="${SYNCOPATED_FIRSTBOOT_MACHINE_MARKER:-$_machine_marker_home/.initial-firstboot}"
if [[ -f "$_machine_marker" ]]; then
  return 0 2>/dev/null || exit 0
fi

# Ensure deterministic PATH and rbenv shims are loaded before firstboot runs
# (syncopated-firstboot.sh collates before syncopated-path.sh in /etc/profile.d/).
_path_hook="${SYNCOPATED_PATH_HOOK:-/etc/profile.d/syncopated-path.sh}"
if [[ -r "$_path_hook" ]]; then
  # shellcheck source=/dev/null
  . "$_path_hook"
fi

# Execute stage 1 of syncopated-firstboot
_firstboot_bin="${SYNCOPATED_FIRSTBOOT_BIN:-/usr/local/bin/syncopated-firstboot}"
if [[ -x "$_firstboot_bin" ]]; then
  "$_firstboot_bin" --stage 1
fi
