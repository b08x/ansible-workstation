# What the output is good for

Each use case below is marked with how it was checked:

- **Verified** — the command was run against the stored trace; its real output is shown.
- **Supported by code, not executed** — the code path exists and was read, but nothing in this repo exercises it.
- **Not available** — sometimes assumed to work, but not implemented here.

All measurements come from run `2ab5a61b` (2026-09-10,
`openrouter/ibm-granite/granite-4.2-8b`, 11 subjects). **This is a sample of one
run on one model.** Figures are reproducible against that stored trace; they do
not generalise to other models, and per-field rates computed over 9 rows carry
wide uncertainty however precisely they print.

The design rationale for capturing any of this is recorded in
[`docs/pdca/001-llm-analyzer-dspy.md`](../pdca/001-llm-analyzer-dspy.md).

---

## 1. Reading what a playbook actually does — **Verified**

The most immediate use. Each analysis renders to Markdown under `llm_analysis/`
with a parameter table, idempotency verdict and execution logistics. A real file
from the captured run:

```markdown
### Module Signature
- **Module**: ansible.builtin.dnf
- **FQCN**: Qualified

### Parameters
| Parameter | Value | Purpose |
| :--- | :--- | :--- |
| name | dnf-plugins-core | The package name to install |
| state | present | Whether to ensure the package is present |

### Execution Logistics
- **Idempotency**: implicit — The dnf module inherently ensures idempotency when
  state=present; if the package is already installed, no change occurs.
```

*Source: `llm_analysis/20260910_180701_task_9_..._Ensure_dnf_plugins_core_is_installed.md`.*

Each file carries its `Trace:` id, so a rendered page and its stored row can
always be reconciled (`llm_report.py`, written from `llm_analyzer.py:407-414`).

**Worth knowing:** the signature instructs the model to be *non-evaluative* —
"Report factual descriptions only... Do not prescribe rewrites"
(`llm_signatures.py:43-48`). This is documentation of intent, not a code review.
For prescriptive findings, use `ansible-lint` or the local style checker.

## 2. Taking inventory of the store — **Verified**

```
$ python scripts/llm_trainset.py stats
runs            [(1,)]
analyses        [(11,)]
  errored       [(1,)]
  by kind       [('play', 1), ('task', 10)]
  by signature  [('1.0.0', 11)]
judgments       [('heuristic', 9, 0.933)]
```

`by signature` is the one to watch when iterating on prompts — traces from two
signature revisions pooled together make any before/after comparison noise
(`llm_signatures.py:10-13`).

Before any judgments existed, that last line read `n/a (CatalogException)`. That
is the intended degradation, not a fault: `connect()` only creates a view when
matching files exist (`llm_trace_store.py:229-230`).

## 3. Scoring grounding without spending anything — **Verified**

The most useful non-obvious capability. `evaluate` scores every captured
prediction against gold labels **parsed from the task YAML**, with no model calls
at all:

```
$ python scripts/llm_trainset.py evaluate
metric v1.0.0   n=9   skipped=0
  mean   0.933
  median 1.000
  min    0.650    max 1.000
  >=0.9  7/9

  per-field accuracy (worst first):
    parameters             0.778
    idempotency            0.889
    change_detection       0.889
    module                 1.000
    is_fqcn                1.000
    conditions             1.000
    loop                   1.000
    delegation             1.000
    privilege_escalation   1.000
    error_handling         1.000
```

This ran with no network access. It is free and instant, and it re-scores history
— so a metric change can be applied retroactively to every trace ever captured.

**How gold is free.** An Ansible task is a structured document. Module name, FQCN
status, parameter names, and the presence of `when` / `loop` / `become` /
`register` / `delegate_to` / `ignore_errors` are facts recoverable by parsing,
using Ansible's own `ModuleArgsParser` — which handles `k=v` shorthand and the
`args:` block correctly (`llm_metrics.py:13-22`). That covers 10 of the 13 output
fields. Weights are in `llm_metrics.py:60-71`; `module` and `parameters` carry
0.25 and 0.20 because getting either wrong means the analysis is about a
different task.

**What it does not measure — stated in the source, not discovered here.** This is
a *proxy metric*. `goal`, `role_in_play` and `idempotency_mechanism` are the
fields with actual value-add, and **none of them are checked**
(`llm_metrics.py:24-31`). A model can score 1.0 structurally and still write
vacuous prose — the source names this as the classic Goodhart failure. Read the
0.933 above as "this model reliably reports the right module and parameters", not
"the analyses are good".

## 4. Converting the log into a labelled dataset — **Verified**

```
$ python scripts/llm_trainset.py backfill
wrote 9 heuristic judgments -> llm_analysis/traces/judgments/heuristic.jsonl
```

Judgments are stored separately from analyses on purpose: labels arrive later
than the prediction, may arrive more than once, and may come from a human, an LLM
judge, or a heuristic — none of which a column on `analyses` could express
(`llm_trace_store.py:165-171`).

After backfill, `--require-judgment` selects on a real score:

```
$ python scripts/llm_trainset.py examples --require-judgment --min-score 1.0
6 examples (task, gold=derived)
```

6 of 9 scored a perfect 1.0. The heuristic average, 0.933, matches `evaluate`'s
mean exactly — as it must, since both call `score_task`.

## 5. Building a DSPy trainset — **Verified (construction only)**

```
$ python scripts/llm_trainset.py examples --limit 5
5 examples (task, gold=derived)
inputs: ['style_observations', 'task_yaml']
labels: ['change_detection', 'conditions', 'delegation', 'error_handling',
         'idempotency', 'is_fqcn', 'loop', 'module', 'parameters',
         'privilege_escalation']
```

Real `dspy.Example` objects with inputs and labels correctly separated
(`scripts/llm_trainset.py:103-135`).

**The default matters.** `--gold-source derived` labels from the YAML;
`captured` reuses the model's own output. Training on `captured` teaches an
optimiser to reproduce its current mistakes, which is why `derived` is the
default and `captured` is documented as inspection-only
(`scripts/llm_trainset.py:11-14`, `112-116`).

## 6. Cost and latency accounting — **Verified**

`sql` runs arbitrary DuckDB against the store:

```
$ python scripts/llm_trainset.py sql \
    "SELECT kind, round(avg(latency_ms)) lat, sum(prompt_tokens) pt,
            sum(completion_tokens) ct FROM analyses GROUP BY 1"
('play', 59968.0, 1196, 5800)
('task', 63606.0, 11883, 63758)
```

This is how the latency and token figures elsewhere in these docs were obtained.
Because views read the JSONL directly, a query can run **while a playbook is
still writing** and will see every record flushed so far without blocking the
writer (`llm_trace_store.py:216-218`).

See [tuning.md](tuning.md) for a caveat on interpreting the token columns: one
recorded value exceeds the configured per-response cap, so these appear to
aggregate multiple underlying calls.

## 7. Catching model failure modes — **Verified**

Failed analyses are recorded *before* the error check, so failures are captured
rather than lost (`llm_analyzer.py:378-390`):

```
$ python scripts/llm_trainset.py sql \
    "SELECT name, substr(error,1,150) FROM analyses WHERE error IS NOT NULL"
('Display ansible_distribution',
 "AdapterParseError: The LM returned an empty or null response.
  LM Response: {'text': None, 'rea...")
```

That one row is a real instance of exactly the failure the startup probe is built
to detect: `text: None` with a `reasoning_content` preamble, from a model that
spent its budget before answering (`llm_engine.py:138-147`, `151-163`). One
subject in eleven — roughly 9% — produced nothing usable. Without the trace
store this would have been an absent Markdown file and nothing else.

## 8. Comparing models or prompt revisions — **Supported by code, not executed**

The schema carries `model`, `provider`, `signature_version` and `schema_version`
on every row (`llm_trace_store.py:124-148`, confirmed against the stored JSONL),
and `evaluate` is free and retroactive, so the comparison is a `GROUP BY` away.

**Not demonstrated.** The store holds one model and one signature version. Every
figure in these documents is `granite-4.2-8b` at `signature 1.0.0`. No
cross-model claim is made here because none can be supported.

**A gap worth knowing about.** `METRIC_VERSION` is printed by `evaluate` but
never persisted — it appears on neither the analysis row nor the judgment row
(`llm_trace_store.py:124-148`, `172-178`; confirmed by reading back the stored
JSONL keys). Since judgments are written by `backfill` and the metric is
versioned independently, a store can accumulate judgment rows from two metric
revisions with nothing on disk distinguishing them. `signature_version` has
exactly this protection; the metric does not.

## 9. Optimising the prompt with DSPy — **Supported by code, not executed**

This is the stated end goal (`docs/pdca/001-llm-analyzer-dspy.md`), and the
pieces exist:

| Piece | Location | State |
| :--- | :--- | :--- |
| Addressable signatures | `llm_signatures.py:42-127` | Built |
| Trainset builder | `scripts/llm_trainset.py:103-135` | Verified working |
| `task_metric` | `llm_metrics.py:355` | Defined |
| `task_feedback_metric` (GEPA) | `llm_metrics.py:369` | Defined |
| `judge_metric` (LLM judge) | `llm_metrics.py:412` | Defined |
| `composite_metric` | `llm_metrics.py:442` | Defined |
| Judge signature | `llm_signatures.py:131-167` | Defined |
| **An optimiser run** | — | **Absent** |

**No optimiser is wired up in this repository.** A search for `.compile(`,
`MIPROv2`, `GEPA`, `BootstrapFewShot` or `teleprompt` finds matches only inside
docstrings describing intended use (`llm_metrics.py:358-359`, `377-379`).
`scripts/llm_trainset.py` imports `extract_gold`, `score_task` and
`METRIC_VERSION` — not the metric functions (`scripts/llm_trainset.py:31`).

So the honest statement is: the trainset and metrics are ready to hand to an
optimiser, and nothing here has handed them to one. Wiring that up is unwritten
work, not a documented feature. Neither `judge_metric` nor `composite_metric` is
called by any script — using either means importing it yourself, and
`judge_metric` costs one LM call per example (`llm_metrics.py:413`).

## 10. Human quality labels — **Supported by code, not executed**

`record_judgment` accepts any `source` string (`llm_trace_store.py:157-185`), so
human labels coexist with heuristic ones and `stats` reports them separately.

The store currently holds only the 9 `heuristic` rows written in §4. The metrics
docstring notes that an earlier attempt at human labelling produced exactly one
judgment across 22 traces (`llm_metrics.py:9-11`) — which is the reason the
derived-gold approach exists.

---

## What this is not

- **Not a linter.** The signature forbids prescribing rewrites
  (`llm_signatures.py:43-48`). `ansible-lint` is the tool for findings you act on.
- **Not a correctness check.** It describes what a task says it does, from the
  YAML alone. It never sees execution results.
- **Not free.** ~1,320 prompt and ~7,084 completion tokens per task, and with
  `async_workers = 0` a median 58.9s added per task.
- **Not deterministic.** `temperature` defaults to 0.4; re-analysing the same
  task will not reproduce the same prose.
