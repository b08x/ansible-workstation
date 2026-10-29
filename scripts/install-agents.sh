#!/usr/bin/env bash
# scripts/install-agents.sh — Install Antigravity CLI agents globally or check status
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENTS_DIR="${REPO_ROOT}/.agents/agents"
TARGET_DIR="${HOME}/.gemini/agents"

MODE="copy"
ACTION="install"

for arg in "$@"; do
  case "$arg" in
    --symlink|-s)
      MODE="symlink"
      ;;
    --uninstall|-u)
      ACTION="uninstall"
      ;;
    --check|-c)
      ACTION="check"
      ;;
    --help|-h)
      echo "Usage: $0 [--symlink] [--uninstall] [--check]"
      echo "  --symlink, -s    Symlink agent definitions to ~/.gemini/agents/ (default is copy)"
      echo "  --uninstall, -u  Remove agents from ~/.gemini/agents/"
      echo "  --check, -c      Verify agent discovery"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      exit 1
      ;;
  esac
done

if [ "${ACTION}" = "uninstall" ]; then
  echo "Uninstalling syncopated agents from ${TARGET_DIR}..."
  for file in "${AGENTS_DIR}"/*.md; do
    name="$(basename "$file")"
    if [ -e "${TARGET_DIR}/${name}" ] || [ -L "${TARGET_DIR}/${name}" ]; then
      rm -f "${TARGET_DIR}/${name}"
      echo "  Removed: ${TARGET_DIR}/${name}"
    fi
  done
  echo "Uninstall complete."
  exit 0
fi

if [ "${ACTION}" = "check" ]; then
  echo "Checking agent availability with 'agy agents'..."
  if command -v agy >/dev/null 2>&1; then
    agy agents | grep syncopated
  else
    echo "agy CLI not found on PATH."
  fi
  exit 0
fi

mkdir -p "${TARGET_DIR}"
echo "Installing syncopated agents to ${TARGET_DIR} (${MODE} mode)..."

for file in "${AGENTS_DIR}"/*.md; do
  name="$(basename "$file")"
  target="${TARGET_DIR}/${name}"

  if [ "${MODE}" = "symlink" ]; then
    ln -sf "${file}" "${target}"
    echo "  Symlinked: ${target} -> ${file}"
  else
    cp -f "${file}" "${target}"
    echo "  Copied: ${target}"
  fi
done

echo ""
echo "Installation complete. Verify with:"
echo "  agy agents | grep syncopated"
echo "Start the orchestrator with:"
echo "  agy --agent syncopated-lead"
