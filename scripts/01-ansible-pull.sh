#!/usr/bin/env bash
# 01-ansible-pull.sh: apply the Syncopated user space playbook with ansible-pull
# (user tools, environment paths, and unprivileged user configuration).
#
# Optional bootstrap step: asks before doing anything and exits 2 (skipped)
# when declined or when no terminal is attached.
# Runs without a spinner (no run_item): gum spin hides stdin, which would
# hide the prompts.
# Override: SYNCOPATED_ANSIBLE_PULL=yes|no answers the opt-in prompt.
#
# Additional overrides: SYNCOPATED_ANSIBLE_PULL_URL,
# SYNCOPATED_ANSIBLE_PULL_PLAYBOOK, SYNCOPATED_ANSIBLE_PULL_CHECKOUT,
# SYNCOPATED_ANSIBLE_PULL_BRANCH, SYNCOPATED_ANSIBLE_PULL_INVENTORY.

set -uo pipefail

THEME_FILE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/syncopated-theme.sh"
if [[ -f "$THEME_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$THEME_FILE"
elif [[ -f "${HOME}/.config/yadm/scripts/syncopated-theme.sh" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.config/yadm/scripts/syncopated-theme.sh"
else
  info() { echo "[INFO] $*"; }
  warn() { echo "[WARN] $*" >&2; }
  err() { echo "[ERROR] $*" >&2; }
  ok() { echo "[OK] $*"; }
  have_gum() { command -v gum >/dev/null 2>&1; }
  have_systemd_cat() { command -v systemd-cat >/dev/null 2>&1; }
  VIOLET=("#7E57C2")
  RC_SKIPPED=2
  RC_FAILED=1
fi

: "${SYNCOPATED_STEP:=ansible-pull}"

# Repository holding the playbook (defaults to the GitLab workstation remote).
PLAYBOOK_URL=${SYNCOPATED_ANSIBLE_PULL_URL-https://gitlab.com/syncopatedX/workstation.git}
# Playbook file inside the repository.
PLAYBOOK=${SYNCOPATED_ANSIBLE_PULL_PLAYBOOK:-local.yml}
# Local checkout directory used by ansible-pull.
CHECKOUT=${SYNCOPATED_ANSIBLE_PULL_CHECKOUT:-${XDG_CACHE_HOME:-$HOME/.cache}/syncopated/ansible-pull}
# Optional branch/tag/commit override.
BRANCH=${SYNCOPATED_ANSIBLE_PULL_BRANCH:-development}
# Target inventory for ansible-pull (defaults to local hostname with trailing comma).
LOCAL_HOSTNAME=${HOSTNAME:-$(hostname 2>/dev/null || uname -n)}
INVENTORY=${SYNCOPATED_ANSIBLE_PULL_INVENTORY:-"${LOCAL_HOSTNAME},"}
# Ensure inline inventory has a trailing comma if not an existing file and not already comma-separated.
if [[ -n $INVENTORY && ! -e $INVENTORY && $INVENTORY != *,* ]]; then
  INVENTORY="${INVENTORY},"
fi

# want_ansible_pull : succeed when the user opts in to applying the user playbook.
# Defaults to no; without a terminal or gum there is no one to ask.
want_ansible_pull() {
  case ${SYNCOPATED_ANSIBLE_PULL:-} in
    yes|true|1) return 0 ;;
    no|false|0) return 1 ;;
  esac
  [[ -t 0 && -t 1 ]] && have_gum || return 1
  gum confirm --default=true --prompt.foreground "${VIOLET[0]}" \
    "Apply user configuration playbook via ansible-pull (unprivileged)?"
}

main() {
  if ! want_ansible_pull; then
    info "ansible-pull: user playbook skipped"
    return "${RC_SKIPPED:-2}"
  fi
  if [[ -z $PLAYBOOK_URL ]]; then
    info "ansible-pull: no user playbook configured yet"
    return "${RC_SKIPPED:-2}"
  fi
  if ! command -v ansible-pull >/dev/null 2>&1; then
    warn "ansible-pull is not installed; user playbook skipped"
    return "${RC_SKIPPED:-2}"
  fi
  info "Applying $PLAYBOOK (user tags) from $PLAYBOOK_URL"
  mkdir -p "$CHECKOUT"
  export ANSIBLE_STDOUT_CALLBACK=default
  export ANSIBLE_INVENTORY_ENABLED="host_list,script,auto,yaml,toml,ini"
  export ANSIBLE_LOG_PATH="${CHECKOUT}/ansible.log"
  local -a pull_args=(
    --url "$PLAYBOOK_URL"
    --directory "$CHECKOUT"
  )
  if [[ -n $INVENTORY ]]; then
    pull_args+=(--inventory "$INVENTORY")
  fi
  if [[ -n $BRANCH ]]; then
    pull_args+=(--checkout "$BRANCH")
  fi
  pull_args+=(--tags user "$PLAYBOOK")

  local pull_rc=0
  if have_systemd_cat; then
    ansible-pull "${pull_args[@]}" 2>&1 | tee >(systemd_cat_log info)
    pull_rc=${PIPESTATUS[0]}
  else
    ansible-pull "${pull_args[@]}"
    pull_rc=$?
  fi

  if ((pull_rc != 0)); then
    err "ansible-pull failed"
    return "${RC_FAILED:-1}"
  fi
  ok "User playbook applied"
}

main "$@"
