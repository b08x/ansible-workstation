# Syncopated Agent Workflow — Mistral Vibe Harness

This directory contains configuration files and system prompts for running the Syncopated Workstation 6-phase multi-agent pipeline using **Mistral Vibe**.

## Directory Layout

```text
.vibe/
├── agents/
│   ├── syncopated-lead.toml               # Orchestrator agent profile (user-selectable)
│   ├── syncopated-lead-specifier.toml     # Phase 1: Design subagent
│   ├── syncopated-lead-implementer.toml   # Phase 2: Write subagent
│   ├── syncopated-lead-cleaner.toml       # Phase 3: Refactor subagent
│   ├── syncopated-lead-hardener.toml      # Phase 4: Assert + Secure subagent
│   ├── syncopated-lead-qa.toml            # Phase 5: Verify subagent
│   └── syncopated-lead-architect.toml     # Phase 6: Audit + Govern subagent
└── prompts/
    ├── syncopated-lead.md                 # System prompt for lead orchestrator
    └── syncopated-lead-{phase}.md         # System prompts for phases 1 through 6
```

## Running with Mistral Vibe

Start Mistral Vibe in the repository root with the lead agent selected:

```bash
vibe --agent syncopated-lead
```

The lead agent delegates work through the six phases via Vibe's `task` tool, checking quality gates at each step.

---

## Antigravity CLI (`agy`) Equivalent

For **Google Antigravity CLI (`agy`)**, native agent definitions are located in:

```text
.agents/agents/
├── syncopated-lead.md                     # Antigravity lead orchestrator
├── syncopated-lead-specifier.md           # Phase 1: Design subagent
├── syncopated-lead-implementer.md         # Phase 2: Write subagent
├── syncopated-lead-cleaner.md             # Phase 3: Refactor subagent
├── syncopated-lead-hardener.md            # Phase 4: Assert + Secure subagent
├── syncopated-lead-qa.md                  # Phase 5: Verify subagent
└── syncopated-lead-architect.md           # Phase 6: Audit + Govern subagent
```

Start the Antigravity orchestrator with:

```bash
agy --agent syncopated-lead
```

Both harnesses share identical methodology, the 15 Ansible design patterns, and skills (`.agents/skills/syncopated` and `.agents/skills/ansible-patterns-anti-patterns`).
