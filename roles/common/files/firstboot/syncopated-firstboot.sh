#!/bin/bash
# /etc/profile.d/syncopated-firstboot.sh
# Trigger Syncopated user firstboot on interactive shell login if not yet run.

if [[ -n "${BASH_VERSION:-}" && $- == *i* ]]; then
  # Only run if firstboot.done does not exist and user is unprivileged (UID >= 1000)
  if [[ $(id -u) -ge 1000 ]]; then
    _fb_done="${XDG_STATE_HOME:-$HOME/.local/state}/syncopated/firstboot.done"
    if [[ ! -f "$_fb_done" && -x /usr/local/bin/syncopated-firstboot ]]; then
      # Only launch on interactive console/terminal if not already running in desktop autostart
      if [[ -z "${DESKTOP_AUTOSTART:-}" && -t 0 ]]; then
        /usr/local/bin/syncopated-firstboot
      fi
    fi
    unset _fb_done
  fi
fi
