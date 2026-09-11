#!/usr/bin/env bash
# =============================================================================
# Workstation Bootstrap Orchestrator
# A wonderfully warm, colorful TUI for provisioning your development environment
# =============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (e.g., using sudo)." >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# Configuration & State
# -----------------------------------------------------------------------------

SCRIPT_NAME="$(basename "$0")"
LOG_FILE="/tmp/${SCRIPT_NAME%.*}.log"
STATE_FILE="/tmp/${SCRIPT_NAME%.*}.state"

# Color palette - warm, inviting colors
declare -A COLORS=(
  [primary]="#FA8072"
  [secondary]="#FFD700"
  [success]="#90EE90"
  [error]="#FF6B6B"
  [warning]="#FFA07A"
  [info]="#87CEFA"
  [muted]="#D3D3D3"
  [border]="#FFE4B5"
)

# -----------------------------------------------------------------------------
# Trap Functions & Error Handling
# -----------------------------------------------------------------------------

cleanup() {
  local exit_code=$?
  local signal=$1

  [[ -f "$STATE_FILE" ]] && rm -f "$STATE_FILE"

  if [[ $exit_code -eq 0 ]]; then
    if command_exists gum; then
      echo "" | gum style --foreground "${COLORS[success]}" --border double --padding "1 2" --align center \
        "Bootstrap completed successfully"
    else
      echo "Bootstrap completed successfully"
    fi
  else
    if command_exists gum; then
      echo "" | gum style --foreground "${COLORS[error]}" --border double --padding "1 2" --align center \
        "Bootstrap exited with errors (code: $exit_code)"
      [[ -n "$signal" && "$signal" != "EXIT" ]] && \
        echo "" | gum style --foreground "${COLORS[warning]}" --padding "0 2" --align center \
          "Signal received: $signal"
    else
      echo "Bootstrap exited with errors (code: $exit_code)"
      [[ -n "$signal" && "$signal" != "EXIT" ]] && echo "Signal received: $signal"
    fi
  fi
  exit "$exit_code"
}

handle_interrupt() {
  local signal=$1
  echo "" | gum style --foreground "${COLORS[warning]}" --padding "1 2" --align center \
    "Operation interrupted by user (Ctrl+C)"
  if gum confirm --affirmative "Continue" --negative "Exit" \
    "Do you want to continue the bootstrap process?"; then
    echo "" | gum style --foreground "${COLORS[info]}" --padding "0 2" --align center "Resuming..."
    return 0
  else
    echo "" | gum style --foreground "${COLORS[muted]}" --padding "0 2" --align center "Cleaning up..."
    cleanup "$signal"
  fi
}

handle_error() {
  local cmd="$1"
  local line="$2"
  local exit_code="$3"
  if command_exists gum; then
    echo "" | gum style --foreground "${COLORS[error]}" --border double --padding "1 2" \
      "Error in command: ${cmd}" \
      "Line: ${line}" \
      "Exit code: ${exit_code}"
  else
    echo "ERROR: Command '${cmd}' failed at line ${line} with exit code ${exit_code}"
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Command '${cmd}' failed at line ${line} with exit code ${exit_code}" >> "$LOG_FILE"
  
  if command_exists gum; then
    if gum confirm --affirmative "Continue" --negative "Exit" \
      "Attempt to continue with next steps?"; then
      echo "" | gum style --foreground "${COLORS[warning]}" --padding "0 2" --align center \
        "Continuing with caution..."
      return 0
    else
      cleanup "ERR"
    fi
  else
    cleanup "ERR"
  fi
}

trap 'cleanup "EXIT"' EXIT
trap 'handle_interrupt INT' INT
trap 'handle_interrupt TERM' TERM
trap 'handle_error "$BASH_COMMAND" $LINENO $? ' ERR

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

wipe() {
  tput -S <<!
clear
cup 1
!
}

typewriter() {
  local in_esc=0
  while IFS= read -r -N1 char; do
    if [[ "$char" == $'\e' ]]; then
      in_esc=1
    fi
    echo -n "$char"
    if [[ $in_esc -eq 1 ]]; then
      if [[ "$char" == "m" || "$char" == "K" || "$char" == "H" || "$char" == "J" ]]; then
        in_esc=0
      fi
    else
      sleep 0.001 2>/dev/null || true
    fi
  done
  echo
}


log() {
  local level="$1"
  local message="$2"
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  
  case "$level" in
    info)
      echo "[$timestamp] INFO: $message" >> "$LOG_FILE"
      echo "$message" | gum style --foreground "${COLORS[info]}" --padding "0 1" | typewriter
      ;;
    success)
      echo "[$timestamp] SUCCESS: $message" >> "$LOG_FILE"
      echo "$message" | gum style --foreground "${COLORS[success]}" --padding "0 1" | typewriter
      ;;
    warning)
      echo "[$timestamp] WARNING: $message" >> "$LOG_FILE"
      echo "$message" | gum style --foreground "${COLORS[warning]}" --padding "0 1" | typewriter
      ;;
    error)
      echo "[$timestamp] ERROR: $message" >> "$LOG_FILE"
      echo "$message" | gum style --foreground "${COLORS[error]}" --padding "0 1" | typewriter
      ;;
    *)
      echo "[$timestamp] $level: $message" >> "$LOG_FILE"
      echo "$message" | gum style --foreground "${COLORS[muted]}" --padding "0 1" | typewriter
      ;;
  esac
}

section_header() {
  local title="$1"
  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  echo ""
  echo "$title" | gum style \
    --foreground "${COLORS[primary]}" \
    --border double \
    --border-foreground "${COLORS[border]}" \
    --padding "1 2" \
    --align center \
    --width "$term_width" \
    --bold
}

with_spinner() {
  local description="$1"
  shift
  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  local pad_len=$(( (term_width - ${#description} - 4) / 2 ))
  local padding=""
  for ((i=0; i<pad_len; i++)); do padding="$padding "; done
  gum spin --spinner dot --title "${padding}${description}" -- "$@"
  
  # Flush any leaked terminal capability query responses (like ^[[?2026;2$y) from the input buffer
  while read -r -t 0.1 -n 10000; do :; done || true
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ensure_gum() {
  if ! command_exists gum; then
    echo "============================================================"
    echo "Installing Gum (TUI Toolkit)"
    echo "============================================================"
    echo "Gum not found. Installing from official repository..."
    if dnf install -y https://github.com/charmbracelet/gum/releases/download/v2.0.0/gum-2.0.0-1.x86_64.rpm; then
      if command_exists gum; then
        log success "Gum installed successfully!"
        log info "Gum version: $(gum --version)"
      else
        echo "ERROR: Gum installation failed. Please install manually from https://github.com/charmbracelet/gum"
        exit 1
      fi
    else
      echo "ERROR: Failed to install Gum. This script requires Gum."
      exit 1
    fi
  else
    log info "Gum is already installed: $(gum --version)"
  fi
}

# -----------------------------------------------------------------------------
# Main Bootstrap Functions
# -----------------------------------------------------------------------------

install_core_packages() {
  section_header "Installing Core Development Packages"
  local packages=(
    "ansible-core"
    "ansible-collection-ansible-posix"
    "ansible-collection-ansible-utils"
    "curl"
    "git"
    "gcc"
    "make"
    "procps-ng-devel"
    "micro"
    "htop"
    "uv"
    "python3.14"
    "flatpak"
  )
  log info "The following packages will be installed:"
  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  printf '  %s\n' "${packages[@]}" | gum style --foreground "${COLORS[secondary]}" | typewriter
  
  if with_spinner "Installing core packages..." dnf install -y "${packages[@]}"; then
    log success "Core packages installed"
  else
    log error "Failed to install core packages"
    return 1
  fi
  return 0
}

update_system() {
  section_header "System Update"
  log info "Updating all system packages (this may take a while)..."
  if with_spinner "Running dnf update..." dnf update -y; then
    log success "System updated successfully"
  else
    log warning "System update had issues or was skipped"
  fi
  return 0
}

install_yadm() {
  section_header "Installing YADM (Dotfile Manager)"
  if command_exists yadm; then
    log info "YADM is already installed: $(yadm --version)"
    return 0
  fi
  
  if with_spinner "Downloading and installing YADM..." \
    curl -fLo /usr/local/bin/yadm https://github.com/yadm-dev/yadm/raw/master/yadm \
    && chmod a+x /usr/local/bin/yadm; then
    log success "YADM installed to /usr/local/bin/yadm"
    log info "YADM version: $(/usr/local/bin/yadm --version)"
  else
    log error "Failed to install YADM"
    return 1
  fi
  return 0
}

setup_python_env() {
  section_header "Setting up Python Environment (uv + venv)"

  # --- uv ---------------------------------------------------------------
  # 'uv' is in the core package list, but this script must also work when it
  # is missing (e.g. minimal images or a package list edited later), so an
  # independent installer path exists. Nothing here changes when uv is present.
  if command_exists uv; then
    log info "uv is already installed: $(uv --version | head -1)"
  else
    log warning "uv not found on PATH"
    if with_spinner "Installing uv via dnf..." dnf install -y uv; then
      log success "uv installed via dnf"
    elif with_spinner "Installing uv via official script..." \
      bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'; then
      log success "uv installed to ~/.local/bin via official installer"
      export PATH="$HOME/.local/bin:$PATH"
    else
      log error "Failed to install uv (both dnf and official installer)"
      return 1
    fi
  fi

  # --- venv -------------------------------------------------------------
  # The venv lives in the repo (not /root) so the plugins work from a normal
  # checkout regardless of who ran bootstrap. It uses the system Python.
  local repo_root
  repo_root="$(cd "$(dirname "$0")" && pwd)"
  local venv_dir="${repo_root}/.venv"
  local py_interpreter
  py_interpreter="$(command -v python3.14 || command -v python3)"

  if [[ ! -x "${venv_dir}/bin/python" ]]; then
    log info "Creating venv at ${venv_dir} (interpreter: ${py_interpreter})"
    if ! with_spinner "Creating venv..." uv venv --python "$py_interpreter" "$venv_dir"; then
      log error "Failed to create venv"
      return 1
    fi
  else
    log info "Venv already exists at ${venv_dir}, reusing it"
  fi

  # --- dependencies -------------------------------------------------------
  # PyYAML backs the llm_analyzer callback plugin; dspy (via litellm) backs
  # plugins/callback_utils/llm_engine.py. Pinned in requirements.txt.
  if ! with_spinner "Installing Python dependencies (uv pip)..." \
    uv pip install --python "${venv_dir}/bin/python" \
    -r "${repo_root}/requirements.txt"; then
    log error "Failed to install Python dependencies"
    return 1
  fi
  log success "Python dependencies installed into ${venv_dir}"
  log info "To use it: source ${venv_dir}/bin/activate"
  return 0
}

setup_flatpak() {
  section_header "Setting up Flatpak"
  log info "Adding Flathub remote repository..."
  if with_spinner "Adding remote..." flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo; then
    log success "Flathub remote added successfully"
  else
    log error "Failed to add Flathub remote"
    return 1
  fi
  return 0
}

# -----------------------------------------------------------------------------
# Summary and Finalization
# -----------------------------------------------------------------------------

show_summary() {
  section_header "Bootstrap Complete"
  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  echo "" | gum style --foreground "${COLORS[success]}" --padding "0 1" \
    "Your workstation bootstrap has completed!" | typewriter
  echo "" | gum style --foreground "${COLORS[info]}" --padding "0 1" \
    "Next steps you might want to take:" | typewriter
  local next_steps=(
    "Run 'yadm clone' to set up your dotfiles"
    "Source ./.venv/bin/activate to use the repo Python environment"
    "Run 'dnf autoremove' to clean up unused packages"
    "Review the log file at: $LOG_FILE"
  )
  printf '  %s
' "${next_steps[@]}" | gum style --foreground "${COLORS[secondary]}" --padding "0 1" | typewriter
  echo "" | gum style --foreground "${COLORS[primary]}" --border double --padding "1 2" --align center --width "$term_width" \
    "Thank you for using Workstation Bootstrap Orchestrator!"
}

check_reboot() {
  if [[ -f /var/run/reboot-required ]] || [ -n "$(find /boot -mtime -1 -name 'vmlinuz-*' -print -quit 2>/dev/null)" ]; then
    log warning "A system reboot is highly recommended due to recent updates."
    if gum confirm --affirmative "Reboot Now" --negative "Later" \
      "Reboot the system now?"; then
      log info "Rebooting system..."
      reboot
    fi
  fi
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

main() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bootstrap script started" > "$LOG_FILE"
  
  ensure_gum

  local term_width
  term_width=$(tput cols 2>/dev/null || echo 80)
  wipe
  echo "" | gum style \
    --foreground "${COLORS[primary]}" \
    --border double \
    --border-foreground "${COLORS[border]}" \
    --padding "2 4" \
    --align center \
    --width "$term_width" \
    "Welcome to Workstation Bootstrap Orchestrator"
  echo "" | gum style \
    --foreground "${COLORS[secondary]}" \
    --padding "0 2" \
    --align center \
    --width "$term_width" \
    "A wonderfully warm, colorful TUI for provisioning your development environment"
  echo "" | gum style \
    --foreground "${COLORS[muted]}" \
    --padding "0 2" \
    --align center \
    --width "$term_width" \
    "Press Ctrl+C at any time to interrupt the process" 
  sleep 2

  # Linear execution flow
  wipe
  install_core_packages
  wipe
  update_system
  wipe
  install_yadm
  wipe
  setup_python_env
  wipe
  setup_flatpak
  wipe
  
  show_summary
  check_reboot
  
  # Ensure cleanup runs cleanly
  exit 0
}

main "$@"
