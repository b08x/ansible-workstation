# Workstation Ecosystem: 3-Month Session Intelligence, Commit Forensics & FCA Report
**Period**: August 6, 2026 – November 6, 2026  
**Scope**: `workstation`, `osbuild`, `rpmbuild`, `llmops`, `mistral-vibe`, and legacy `Syncopated/ansible`  
**Data Sources**: `~/.code-insights/data.db` (Schema v18), GitLab (`gitlab.com/syncopatedX/*`), GitHub mirrors  
**Review Status**: SFL Boundary Audited & Epistemically Calibrated (rev2)

---

## Executive Summary & Headline Totals

Over the past 90 days, the workstation infrastructure underwent a fundamental architectural migration, transitioning from a monolithic Ansible repository into a federated 4-repository production ecosystem (`workstation` ⇄ `osbuild` ⇄ `rpmbuild` ⇄ `mistral-vibe`). Simultaneously, the AI development workflow underwent an evolutionary phase-change on **October 29, 2026**: shifting from expensive, long-horizon monolithic Claude Code Opus sessions to autonomous, zero-marginal-cost multi-agent swarms governed by strict verification gates and Systemic Functional Linguistics (SFL) panels.

### Headline Metrics
- **Activity Volume**: 601 recorded sessions · 27,825 conversational messages · 30,855 tool calls.
- **Estimated API Spend**: $1,355.63 gross API-equivalent spend (real outlay was ~3 flat-rate subscriptions).
- **Knowledge Captured**: 1,679 Architectural Decision Records (ADR decisions) · 1,717 post-mortem technical learnings.
- **Delegation Scale**: 301 sessions (50.1%) were specialized autonomous subagents.
- **Intervention Rate**: 368 sessions (61.2%) required course corrections.
- **Context Health**: Only 8 sessions ever triggered context compaction across 3 months (peak: 4 manual + 4 auto-compacts during the 44-hour `osbuild` hardening marathon on Oct 1).

---

## 1. Project Volume, Economics & Tooling Tiers

### Volume & Gross Spend by Project Scope
| Project Scope | Sessions | Messages | Estimated API Cost | Primary Role in Ecosystem |
|---|---|---|---|---|
| **ansible (monorepo path)** | 76 | 5,797 | $528.29 | Initial monorepo baseline (pre-split) |
| **osbuild** | 78 | 4,818 | $491.16 | Image building pipelines & bootc blueprints |
| **mistral-vibe (meta-workspace)** | 146 | 4,799 | $148.90 | Subagent swarm orchestration & dogfooding |
| **workstation-ansible-collection** | 160 | 6,418 | $51.31 | Host provisioning, desktop UI, convergence |
| **rpmbuild** | 29 | 2,198 | $0.00 | RPM packaging specs, mock builds, COPR |
| **ruby-dev** | 33 | 675 | $0.00 | 5-phase Ruby development plugin harness |
| **llmops / devworkstation / others** | ~79 | ~2,820 | ~$136.00 | AI services (Dify, Langfuse, Ollama), testing |

### Cross-Tool Economics & Tooling Tiers
| Tooling Tier | Sessions | Input Tokens | Prompt Cache Hit % | Cost (USD) | Avg Cost/Session | Dominant Model Used |
|---|---|---|---|---|---|---|
| **Claude Code** | 71 | 19.6K raw + 1.5B cached | ~100% | $1,133.55 | $15.97 | Claude Opus 5.5 |
| **mistral-vibe** | 467 | 1.2B | 45.7% | $147.16 | $0.32 | mistral-medium-3.5, glm-5-3 |
| **claude-desktop** | 2 | — | 100% | $74.03 | $37.02 | Claude Opus 5.5 |
| **crush** | 10 | — | 0% | $0.40 | $0.04 | Flat-rate local / API |
| **opencode** | 45 | 3.9M | 93.7% | $0.48 | $0.01 | Flat-rate explore swarms |
| **codex-cli** | 6 | low | — | $0.00 | — | Free tier |

> [!NOTE]
> **Calibrated Spend Analysis**: Claude Code on Opus 5.5 dominated gross financial spend (≈84% of total spend) despite accounting for only ~12% of sessions. The spend reduction in mid-October ($385/wk → $19/wk) was initially initiated by the completion of the multi-day Rocky 9/10 port and `osbuild` monolithic campaigns. The subsequent permanent transition to `mistral-vibe` swarms on Oct 29 decoupled conversational volume from API-tier spend, enabling November's peak volume (9,393 messages in the week of Nov 3) to execute for an API-equivalent spend of only $8.69.

---

## 2. The Four Core Repositories: Session ↔ Commit Forensics

The correlation between **Git commits (mutations in repository history)** and **Code Insights sessions (conversational cognition)** reveals how development changed over time:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SESSION-TO-COMMIT INVERSION (SEP vs NOV)                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ September (Delivery):                                                                  │
│   Workstation: 131 commits / 7 sessions  ──► ~18.7 commits per session                │
│   Rpmbuild:    16 commits / 2 sessions   ──► ~8.0 commits per session                 │
│                                                                                        │
│ November (Gated Convergence):                                                          │
│   Workstation: 42 commits / 90 sessions  ──► ~0.47 commits per session (118 msgs/c)  │
│   Rpmbuild:    12 commits / 27 sessions  ──► ~0.44 commits per session (181 msgs/c)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. `workstation` (Ansible) — The Continuous 10-Month Thread
- **Timeline**: Created on GitLab 2026-09-01 (`initial setup of devworkstation and llmops`) as a deliberate migration away from GitHub. 128 of the GitHub mirror's 212 commits landed that month.
- **Forensic Arc**: In September, the repository was significantly **under-sessioned** (131 commits vs 7 sessions); work occurred inside other repository contexts or direct pushes. In November, this inverted: **90 sessions and 4,946 messages yielded only 42 commits**.
- **Mechanics**: Sessions stopped being how code is written and became **how code is verified as committable**. Atomic commit skills (dozens of 6–16 message sessions) enforced parity gates, PyYAML AST verification, and standalone playbooks extraction (`agent-harness/`).
- **Friction Signature**: `tooling-limitation × environmental` (76) and `stale-assumptions` (72). As the primary host configuration repo, this is where live machine reality (submodules, DNF, pre-commit hooks, systemd) created friction.

### 2. `osbuild` — The Lockstep Build Campaign
- **Timeline**: October was an intensive 1:1 lockstep build campaign: 74 sessions generated 196 commits across GitLab and GitHub.
- **Forensic Arc**: The continuous sequence of blueprints: Fedora 44 templating → OpenSCAP compliance → component package data → the 401-message Oct 11 mega-session → Rocky 10.2 hardened ISO → 132-message reflink `cp` failure fix → generate-only Fedora appliance repair.
- **Handoff**: In November, `osbuild` collapsed to 7 sessions and 18 commits. This was not abandonment; the repository achieved a stable **maintenance posture** governed by the "blueprints stay generate-only" policy, freeing resources for `workstation`'s convergence.

### 3. `rpmbuild` — High-Gated Packaging Swarms
- **Timeline**: In October, 2 sessions and 20 messages produced 16 commits (spec files staged invisibly from other orchestrators).
- **Forensic Arc**: In November, the ratio flipped to **27 sessions and 2,178 messages to produce 12 commits** (~181 messages per commit).
- **Mechanics**: The debut of the `rpm-builder` autonomous 5-phase swarm (`scout` → `specifier` → `engineer` → `verifier` → `publisher`). Dedicated 500+ message mega-sessions on Nov 4 orchestrated the end-to-end RubyMine 2026.2.4 RPM pipeline and Electron app packaging with COPR publication verification.

### 4. `mistral-vibe` — Subject and Instrument Simultaneously
- **Timeline**: 179 lifetime sessions, 8,933 tool calls. November was its heaviest month ever (78 commits, 135 sessions, 4,645 messages).
- **Forensic Arc**: Circular dogfooding in a federated ecosystem. The orchestration harness authored its own components while simultaneously provisioning workstation roles (`tools`, `rpmbuild` prompts).
- **Friction Signature**: Highest friction in the entire dataset (`tooling-limitation × environmental` ×90, `stale-assumptions` ×85). As the platform constructing itself, every environment limit became simultaneously an engine bug and a workflow obstruction.

---

## 3. Formal Concept Analysis (FCA) & Decision Attribute Lattice

In Formal Concept Analysis terms, each milestone event in `session_steps` constitutes an object $g \in G$, mapped to binary attributes $m \in M$ covering Decision Drivers, Target Artifacts, and Execution States.

### Contingency Analysis: Decision Driver vs Target Artifact vs Outcome
| Decision Maker (`driver`) | Target Artifact (`target`) | Total Steps | Success % | Error % | Blocked % | Course Correction % |
|---|---|---|---|---|---|---|
| **LLM_Decide** | `Target_Docs` | 1,091 | 93.5% | 4.5% | 2.0% | 13.5% |
| **LLM_Decide** | `Target_Config` | 524 | 91.2% | 5.9% | 2.9% | 19.1% |
| **LLM_Decide** | `Target_SrcCode` | 393 | 92.1% | 6.1% | 1.8% | 20.9% |
| **LLM_Decide** | `Target_Test` | 228 | **82.0%** | **13.6%** | **4.4%** | **25.4%** |
| **User_Decide** | `Target_Docs` | 281 | 95.0% | 2.8% | 2.1% | 16.4% |
| **User_Decide** | `Target_Config` | 155 | 88.4% | 3.9% | 7.7% | 27.1% |
| **Collab_Decide** | `Target_Docs` | 194 | 94.8% | 1.0% | 4.1% | 23.2% |
| **Collab_Decide** | `Target_Config` | 142 | 97.2% | 1.4% | 1.4% | 23.9% |
| **Collab_Decide** | `Target_Test` | 10 | **94.4%** | **0.0%** | **5.6%** | **10.0%** |
| **Collab_Decide** | `Target_SrcCode` | 55 | 89.1% | 7.3% | 3.6% | **47.3%** |

### Mathematical Concept Lattice Structure
Using the `concepts` Python formal concept engine, the interaction dyads were clustered across 7 formal properties:
- `Vol_High(>100)`: Steps exceeding 100 observations.
- `Succ_High(>90%)`: Baseline operational success rate $\ge 90\%$.
- `Err_Elevated(>5%)`: Execution failure rate exceeding 5%.
- `Block_Elevated(>3%)`: Environmental blocked state rate exceeding 3%.
- `Corr_High(>20%)`: Course correction rate exceeding 20%.
- `Test_Intensive(>25%)`: Test suite invocation frequency $\ge 25\%$.
- `Tool_Intensive(>70%)`: Active tool execution rate $\ge 70\%$.

The resulting **25-node Formal Concept Lattice** decomposes into distinct structural strata:
- **The Operational Foundation (Concept #11, #14)**: High-volume, high-success routine operations (`LLM:Docs`, `LLM:Config`, `User:Docs`, `Collab:Docs`).
- **The Autonomous Test Gaps (Concept #2, #13)**: `LLM:Test` shares intents with elevated error, blocked states, and high corrections (`[Err_Elevated, Block_Elevated, Corr_High, Test_Intensive, Tool_Intensive]`).
- **The Architectural Crucible (Concept #16, #21)**: Source code mutations and collaborative pivots (`Collab:SrcCode`, `LLM:SrcCode`) cluster under high tool usage and elevated course corrections, representing deliberate architectural convergence points.

```
       [Top: Concept #24 (All Objects, ∅ Properties)]
                          /      \
               Concept #20        Concept #23 (Tool_Intensive)
              (Vol_High)               /     \
                /      \     Concept #18      Concept #21 (Corr_High)
          Concept #14  Concept #15               /         \
         (Succ_High)        \             Concept #10    Concept #13 (Test_Intensive)
             |          Concept #11 (Succ+Tool)    \            /
          Concept #4         \                  Concept #2 (LLM:Test)
      (LLM:Config/Src)        \                     /
              \             Concept #1 (LLM:Src)   /
               \                     \            /
                ------------------- Concept #0 -------------------
                           [Bottom: ∅ Objects, All Properties]
```
*Visual graph rendered to [fca-decision-lattice.svg](fca-decision-lattice.svg) ([Graphviz DOT](fca-decision-lattice.dot)).*

### FCA Takeaways (Epistemically Calibrated)
1. **Target_Test Heuristic**: Autonomous LLM test creation demonstrates elevated failure rates ($82.0\%$ success, $N=228$), while collaborative test design shows higher success ($94.4\%$). However, because the collaborative test sample is currently a small pilot ($N=10$), this is an empirically grounded risk-mitigation heuristic rather than a definitive mathematical certainty.
2. **Post-Error Trajectory Calibration**: While consecutive errors compound failure, the data shows that **57.8% of single autonomous syntax/build retries succeed without user intervention**. In contrast, `State_Blocked` (missing tools, permissions) almost never resolves autonomously. The operational rule is therefore: **allow 1 autonomous retry on syntax/execution errors, but mandate immediate escalation on `State_Blocked` or a second consecutive failure**.

---

## 4. The Orchestration Stack: 10-Day Evolutionary Explosion

Between October 26 and November 5, 2026, the orchestration pattern underwent radical specialization:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE CANONICAL 6-PHASE CONTRACT                            │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│   Phase 1    │   Phase 2    │   Phase 3    │   Phase 4    │   Phase 5    │   Phase 6   │
│  Read-Only   │  Specifier   │ Implementer  │   Cleaner    │      QA      │ SFL / GEB   │
│    Scout     │   Drafter    │    Editor    │   Hardener   │  Validator   │ Judge Panel │
│ (non-mutating│ (gated plan  │  (mutation   │ (refactor &  │ (--check dry │ (blind 3-way│
│  paths/git)  │  & bounds)   │ under parity)│  linter fix) │ run on VM)   │ cross-exam) │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

### Operational Reality & Limitations of the 6 Phases
- **Declarative vs Stateful Divergence**: This 6-phase pipeline operates with high fidelity for **documentation, packaging (`rpmbuild`), and greenfield Ansible playbooks**.
- **Check-Mode Boundary**: Phase 5 (`QA/Validator`) running `ansible-playbook --check` is valid only for idempotent templates and package state checks. It **cannot validate stateful kernel/hardware operations** (`gpu`, `akmods`, kernel arguments, systemd restarts) which require real VM testbeds (`gir-virt`).

---

## 5. Cross-Workflow Correlated Insights & Lived Heuristics

1. **Graph Analysis Failures → Documentation Provenance → Doc-Audit Panels**:
   Early failures of graph extraction on large repositories led to the rule: *"Every claim carries a provenance tuple resolvable to an exact codebase anchor."* This contract evolved into the two-pass evidence fact-check gates used by SFL audit panels.
2. **The `find` Denylist & Safe Walk Heuristics**:
   The environmental sandbox denylist blocking the `find` command was the prominent exemplar of environmental tooling friction (which totaled 312 incidents across the ecosystem). Because naive `ls -R` fallbacks dump excessive output into context buffers, agents must use bounded Python walks:
   ```bash
   python3 -c "import os; [print(os.path.join(r, f)) for r, d, fs in os.walk('.') for f in fs if f.endswith('.yml')][:50]"
   ```
3. **Schema Confidence Scores → Metafunction Splitting**:
   Splitting document judging into three blind specialists (Ideational, Interpersonal, Textual) mirrors the formal schema extraction lessons from August: single monolithic judges conflate tone with factual accuracy.
4. **Atomic Commit Enforcement → Phased Remote Publication**:
   The `git-commit` skill's rule (*"split commits until logical units are atomic"*) directly shaped the November `rpm-builder` publication loops, where spec staging, mock builds, and COPR publishing were split into distinct verifiable stages.
5. **Context Loss Shifted from Compaction to Thin Handoffs**:
   Context degradation initially manifested as memory compaction (monolithic sessions). Post-pivot, compaction ceased (only 8 lifetime instances), but context loss reappeared as "thin subagent briefs" where delegators omitted critical paths or test constraints.
6. **Backward Root-Cause Tracing ↔ Forward Staged Markers**:
   Debugging transcribe.cpp SYCL backend issues required tracing backward through deep call stacks. The November two-stage firstboot architecture inverted this: forward-staged markers (`~/.initial-firstboot`) create explicit state boundaries so failures are immediately localized. To survive network outages during Stage 2, markers must record stage-level exit statuses rather than simple 0-byte existence.
7. **Verification-as-a-Workflow Emerged from Delegation**:
   Formal verification workflows did not exist when a single human worked with a single prompt. They emerged organically when subagents required checkable, unambiguous definitions of done.
