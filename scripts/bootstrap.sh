#!/usr/bin/env bash
# ==============================================================================
# scripts/bootstrap.sh
# Syncopated Workstation Bootstrap - Stage 1 (Initial Setup & Upgrade)
#
# Standalone bootstrap script suitable for hosting as a GitLab snippet or Gist.
# 1. Validates root/sudo elevation.
# 2. Installs minimal prerequisites (git, ansible-core, collections).
# 3. Performs a full system upgrade via dnf upgrade -y --refresh.
# 4. Stages Stage 2 runner and systemd unit.
# 5. Enables syncopated-bootstrap-root.service and prompts for reboot.
# ==============================================================================

set -euo pipefail

WORKSTATION_REPO="${WORKSTATION_REPO:-https://gitlab.com/syncopatedX/workstation.git}"
WORKSTATION_BRANCH="${WORKSTATION_BRANCH:-development}"

# Validate effective root permissions
if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: This bootstrap script must be run as root or with sudo." >&2
  echo "Example: sudo bash $0" >&2
  exit 1
fi

echo "============================================================"
echo "Stage 1: Syncopated Workstation Bootstrap & System Upgrade"
echo "Target Repository: ${WORKSTATION_REPO}"
echo "Target Branch:     ${WORKSTATION_BRANCH}"
echo "============================================================"

# Install minimal prerequisites
echo "--> Installing bootstrap prerequisites (git, ansible-core, collections, python3-dnf, python3-rich)..."
dnf install -y \
  git \
  ansible-core \
  ansible-collection-ansible-posix \
  ansible-collection-community-general \
  python3-dnf \
  python3-rich

# Execute full system upgrade
echo "--> Performing full system upgrade..."
dnf upgrade -y --refresh

# Write Stage 2 runner
echo "--> Staging Stage 2 runner (/usr/local/sbin/syncopated-bootstrap-root.sh)..."
cat << EOF > /usr/local/sbin/syncopated-bootstrap-root.sh
#!/usr/bin/env bash
# ==============================================================================
# syncopated-bootstrap-root.sh
# Stage 2: Automated root system convergence via ansible-pull.
# ==============================================================================

set -euo pipefail

WORKSTATION_REPO="\${WORKSTATION_REPO:-${WORKSTATION_REPO}}"
WORKSTATION_BRANCH="\${WORKSTATION_BRANCH:-${WORKSTATION_BRANCH}}"
PLAYBOOK="local.yml"

echo "============================================================"
echo "Starting Stage 2: Syncopated Root System Provisioning"
echo "Repository: \${WORKSTATION_REPO}"
echo "Branch:     \${WORKSTATION_BRANCH}"
echo "Playbook:   \${PLAYBOOK}"
echo "============================================================"

LOCAL_HOSTNAME="\${HOSTNAME:-\$(hostname 2>/dev/null || uname -n)}"
INVENTORY="\${LOCAL_HOSTNAME},"
export ANSIBLE_STDOUT_CALLBACK=default
export ANSIBLE_INVENTORY_ENABLED="host_list,script,auto,yaml,toml,ini"

pull_rc=0
ansible-pull \\
  -i "\${INVENTORY}" \\
  -U "\${WORKSTATION_REPO}" \\
  -C "\${WORKSTATION_BRANCH}" \\
  --tags system \\
  "\${PLAYBOOK}" || pull_rc=\$?

if [[ "\$pull_rc" -eq 0 ]]; then
  echo "============================================================"
  echo "Stage 2: Root system convergence completed successfully!"
  echo "Disabling syncopated-bootstrap-root.service..."
  echo "============================================================"

  systemctl disable syncopated-bootstrap-root.service 2>/dev/null || true
  rm -f /etc/systemd/system/syncopated-bootstrap-root.service
  systemctl daemon-reload 2>/dev/null || true

  if [[ -e /dev/tty1 ]]; then
    read -t 15 -rp "Press Enter to reboot, or wait 15 seconds... " </dev/tty1 || true
  else
    sleep 5
  fi
  systemctl reboot
else
  echo "============================================================" >&2
  echo "ERROR: Stage 2 root provisioning failed with exit code \${pull_rc}!" >&2
  echo "syncopated-bootstrap-root.service remains enabled for investigation." >&2
  echo "Review the log output above or journalctl -u syncopated-bootstrap-root.service" >&2
  echo "============================================================" >&2

  if [[ -e /dev/tty1 ]]; then
    read -rp "Press Enter to acknowledge error and pause on console: " </dev/tty1 || true
  fi
  exit "\$pull_rc"
fi
EOF

chmod 0755 /usr/local/sbin/syncopated-bootstrap-root.sh

# Write Stage 2 systemd service
echo "--> Staging Stage 2 systemd unit (/etc/systemd/system/syncopated-bootstrap-root.service)..."
cat << 'EOF' > /etc/systemd/system/syncopated-bootstrap-root.service
[Unit]
Description=Syncopated Workstation Root Bootstrap (Stage 2)
After=network-online.target
Wants=network-online.target
Conflicts=getty@tty1.service

[Service]
Type=oneshot
StandardOutput=journal+console
StandardError=journal+console
StandardInput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
ExecStart=/usr/local/sbin/syncopated-bootstrap-root.sh

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable Stage 2 unit
echo "--> Enabling syncopated-bootstrap-root.service..."
systemctl daemon-reload
systemctl enable syncopated-bootstrap-root.service

echo "============================================================"
echo "Stage 1 complete: Prerequisites installed and system upgraded."
echo "Stage 2 systemd service enabled for post-reboot convergence."
echo "============================================================"

if [[ -t 0 ]]; then
  read -t 15 -rp "Press Enter to reboot, or wait 15 seconds: " || true
elif [[ -e /dev/tty ]]; then
  read -t 15 -rp "Press Enter to reboot, or wait 15 seconds: " </dev/tty 2>/dev/null || true
else
  sleep 2
fi

systemctl reboot
