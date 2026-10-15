#!/usr/bin/env bash
# ==============================================================================
# syncopated-bootstrap-root.sh
# Stage 2: Automated root system convergence via ansible-pull.
# ==============================================================================

set -euo pipefail

WORKSTATION_REPO="${WORKSTATION_REPO:-https://gitlab.com/syncopatedX/workstation.git}"
WORKSTATION_BRANCH="${WORKSTATION_BRANCH:-development}"
PLAYBOOK="local.yml"

echo "============================================================"
echo "Starting Stage 2: Syncopated Root System Provisioning"
echo "Repository: ${WORKSTATION_REPO}"
echo "Branch:     ${WORKSTATION_BRANCH}"
echo "Playbook:   ${PLAYBOOK}"
echo "============================================================"

LOCAL_HOSTNAME="${HOSTNAME:-$(hostname 2>/dev/null || uname -n)}"
INVENTORY="${LOCAL_HOSTNAME},"
export ANSIBLE_STDOUT_CALLBACK=default
export ANSIBLE_INVENTORY_ENABLED="host_list,script,auto,yaml,toml,ini"
export ANSIBLE_LOG_PATH="/var/log/ansible-bootstrap.log"

pull_rc=0
ansible-pull \
  -i "${INVENTORY}" \
  -U "${WORKSTATION_REPO}" \
  -C "${WORKSTATION_BRANCH}" \
  --tags system \
  "${PLAYBOOK}" || pull_rc=$?

if [[ "$pull_rc" -eq 0 ]]; then
  echo "============================================================"
  echo "Stage 2: Root system convergence completed successfully!"
  echo "Disabling syncopated-bootstrap-root.service..."
  echo "============================================================"

  touch /var/log/syncopated-stage2.done
  systemctl disable syncopated-bootstrap-root.service 2>/dev/null || true

  if [[ -e /dev/tty1 && -t 0 ]]; then
    read -t 10 -rp "Press Enter to reboot, or wait 10 seconds... " </dev/tty1 || true
  else
    sleep 3
  fi
  systemctl reboot
else
  echo "============================================================" >&2
  echo "ERROR: Stage 2 root provisioning failed with exit code ${pull_rc}!" >&2
  echo "syncopated-bootstrap-root.service remains enabled for investigation." >&2
  echo "Review the log output above or journalctl -u syncopated-bootstrap-root.service" >&2
  echo "============================================================" >&2

  if [[ -e /dev/tty1 ]]; then
    read -rp "Press Enter to acknowledge error and pause on console: " </dev/tty1 || true
  fi
  exit "$pull_rc"
fi
