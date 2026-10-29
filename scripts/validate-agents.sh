#!/usr/bin/env bash
# scripts/validate-agents.sh — Validate Antigravity CLI agent definitions
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================================="
echo " Validating Antigravity CLI Agents in .agents/agents/"
echo "=========================================================="

FAILED=0

EXPECTED_AGENTS=(
  "syncopated-lead"
  "syncopated-lead-specifier"
  "syncopated-lead-implementer"
  "syncopated-lead-cleaner"
  "syncopated-lead-hardener"
  "syncopated-lead-qa"
  "syncopated-lead-architect"
)

# 1. Check file existence and YAML frontmatter
echo -n "1. Checking agent markdown files and YAML frontmatter... "
for agent in "${EXPECTED_AGENTS[@]}"; do
  file=".agents/agents/${agent}.md"
  if [ ! -f "${file}" ]; then
    echo -e "\n${RED}[FAIL] Missing file: ${file}${NC}"
    FAILED=1
    continue
  fi

  # Check frontmatter delimiters
  if ! head -n 1 "${file}" | grep -q "^---$"; then
    echo -e "\n${RED}[FAIL] ${file} does not start with '---' frontmatter delimiter${NC}"
    FAILED=1
  fi

  # Check name
  name_val=$(grep -E "^name:[[:space:]]*" "${file}" | head -n 1 | sed -E 's/^name:[[:space:]]*//' | tr -d '"'\'' ')
  if [ "${name_val}" != "${agent}" ]; then
    echo -e "\n${RED}[FAIL] ${file} frontmatter name '${name_val}' does not match '${agent}'${NC}"
    FAILED=1
  fi

  # Check description
  if ! grep -q -E "^description:[[:space:]]*" "${file}"; then
    echo -e "\n${RED}[FAIL] ${file} missing 'description:' frontmatter field${NC}"
    FAILED=1
  fi
done

if [ ${FAILED} -eq 0 ]; then
  echo -e "${GREEN}[OK]${NC} All 7 agent files valid."
fi

# 2. Check skill dependencies
echo -n "2. Checking required skill references... "
REQUIRED_SKILLS=(
  ".agents/skills/syncopated/SKILL.md"
  ".agents/skills/ansible-patterns-anti-patterns/SKILL.md"
)
for skill in "${REQUIRED_SKILLS[@]}"; do
  if [ ! -f "${skill}" ]; then
    echo -e "\n${RED}[FAIL] Missing required skill: ${skill}${NC}"
    FAILED=1
  fi
done
if [ ${FAILED} -eq 0 ]; then
  echo -e "${GREEN}[OK]${NC} All required skills exist."
fi

# 3. Check for leftover Vibe tokens in agent definitions
echo -n "3. Scanning for legacy / forbidden harness tokens... "
FORBIDDEN_TOKENS=(
  "vibe@mistral.ai"
  "task(agent="
  "mistral.ai"
)
for token in "${FORBIDDEN_TOKENS[@]}"; do
  if grep -rn "${token}" .agents/agents/ >/dev/null 2>&1; then
    echo -e "\n${RED}[FAIL] Found forbidden token '${token}' in .agents/agents/${NC}"
    grep -rn "${token}" .agents/agents/
    FAILED=1
  fi
done
if [ ${FAILED} -eq 0 ]; then
  echo -e "${GREEN}[OK]${NC} Clean of forbidden harness tokens."
fi

# 4. Check discovery via agy agents
echo -n "4. Verifying agent discovery with 'agy agents'... "
if command -v agy >/dev/null 2>&1; then
  DISCOVERED=$(agy agents)
  for agent in "${EXPECTED_AGENTS[@]}"; do
    if ! echo "${DISCOVERED}" | grep -qx "${agent}"; then
      echo -e "\n${RED}[FAIL] 'agy agents' did not discover: ${agent}${NC}"
      FAILED=1
    fi
  done
  if [ ${FAILED} -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} All 7 agents discovered by agy CLI."
  fi
else
  echo -e "${YELLOW}[SKIP] agy command not found on PATH${NC}"
fi

echo "=========================================================="
if [ ${FAILED} -eq 0 ]; then
  echo -e "${GREEN}SUCCESS: All Antigravity CLI agents passed validation!${NC}"
  exit 0
else
  echo -e "${RED}FAILURE: One or more validation checks failed.${NC}"
  exit 1
fi
