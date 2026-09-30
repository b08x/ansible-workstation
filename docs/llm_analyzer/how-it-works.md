# How llm_analyzer works

A walkthrough in the order events actually happen. Citations are `file:line`
against the working tree.

## The shape of the problem

Ansible callbacks are not passive observers. `v2_playbook_on_task_start` is
called on Ansible's own main thread, and Ansible waits for it to return before
dispatching the task. Anything slow in that handler is added directly to the
playbook's wall-clock time, once per task.

An LLM round trip is slow. In the captured run, a single analysis took a median
of **58.9 seconds**, with a maximum of 126.2 seconds:

```
$ python scripts/llm_trainset.py sql \
    "SELECT round(min(latency_ms)/1000,1) min_s, round(median(latency_ms)/1000,1) med_s,
            round(max(latency_ms)/1000,1) max_s, round(sum(latency_ms)/1000,1) total_s
     FROM analyses"
(30.9, 58.9, 126.2, 696.0)
```

That run used `async_workers = 0`, so all **696 seconds — 11.6 minutes** of model
time landed on the playbook, for 11 subjects. This single fact explains most of
the plugin's architecture.

## Startup

**1. Ansible loads the plugin.** `CALLBACK_NEEDS_WHITELIST = True`
(`llm_analyzer.py:237`) means it does nothing unless named in `callbacks_enabled`.

**2. Support modules are located.** The helpers live in `plugins/callback_utils/`,
deliberately outside the plugin directory, and are put on `sys.path` at
`llm_analyzer.py:26-36`. If the directory is missing the plugin raises
`ImportError` rather than letting Ansible report the vague "Skipping plugin"
(`llm_analyzer.py:29-34`).

**3. `set_options` builds the engine** (`llm_analyzer.py:253-310`). The
provider-specific environment variable beats `api_key` in `ansible.cfg`
(`llm_analyzer.py:259`).

**4. The provider is probed before the playbook proceeds.** `validate()` sends a
throwaway prompt — `"Reply with the single word: ok"` — and classifies what comes
back (`llm_engine.py:110-148`).

This probe is more careful than it first appears:

- **Retries are disabled for the probe only** (`llm_engine.py:128-129`). A wrong
  model slug is not retryable, and litellm's default retries would turn one
  config typo into several seconds of startup delay.
- **A successful HTTP response is not accepted as success.** A reasoning model
  that spends its whole budget on preamble returns HTTP 200 with
  `finish_reason="length"` and a null message. The probe reads `text`
  specifically and rejects an empty one (`llm_engine.py:138-147`,
  `_probe_text` at `151-163`).
- **Failures are named, not guessed.** `_classify` (`llm_engine.py:166-187`)
  separates a bad model slug from a rejected key from a rate limit from an
  unreachable endpoint — because reporting every startup failure as "bad API key"
  sends you after the one thing that is often fine.

**If validation fails, the plugin disables itself and the playbook continues**
(`llm_analyzer.py:271-284`). It never fails a run.

**5. The run is recorded and the pool is built** (`llm_analyzer.py:296-310`).

## Per task

`v2_playbook_on_task_start` does the minimum that requires the live object
(`llm_analyzer.py:314-328`): serialise the task to YAML and enqueue it.

The serialisation is not an optimisation detail — it is a correctness
requirement. Ansible **mutates and reuses `Task` objects** as the play advances
(`llm_analyzer.py:227-231`), so a worker handed a live object would analyse
whatever that object had become by the time it got scheduled, not the task as
dispatched.

`_task_to_yaml` (`llm_analyzer.py:418-437`) prefers `task.get_ds()` and falls
back to public attributes if that fails.

## On a worker

`_process` (`llm_analyzer.py:367-414`) is a pure function of the captured text:

1. **Style check** — `analyze_style` runs locally, no model involved
   (`llm_style.py:26`). It checks variable naming, task attribute order, tag
   conventions, and a set of "Ansible Way" rules — procedural shell where a
   declarative module exists, overly complex `when`, long lines — several
   carrying a `reference` back to the *Ansible Best Practices: Roles & Modules*
   source (`llm_style.py:219-296`).
2. **LLM call** — the style findings are passed *into* the prompt as an input
   field, so the model comments on them rather than rediscovering them
   (`llm_signatures.py:51-54`, `llm_engine.py:192-204`).
3. **Record the trace** — written before the error check, so failed analyses are
   captured too (`llm_analyzer.py:378-390`).
4. **Render and save Markdown** — skipped when the analysis errored
   (`llm_analyzer.py:388-414`).

Workers bind the LM with `dspy.context` rather than `dspy.configure`
(`llm_engine.py:219-222`): `configure()` records the calling thread as owner and
raises if another thread calls it.

`_run` never raises (`llm_engine.py:206-243`). A failed analysis returns
`({}, meta)` with the error recorded, so one bad response cannot take down a
worker or the playbook.

## What the model is asked for

The prompt is not a string template. It is two `dspy.Signature` classes
(`llm_signatures.py:42-127`) — the task signature declares 13 typed output
fields, including a `list[TaskParameter]` of pydantic models and a
`Literal["explicit", "implicit", "not_handled"]` for idempotency.

Two things follow. First, the output is typed and parsed rather than scraped.
Second, and this is the stated reason for the design
(`llm_signatures.py:5-8`): a `Signature` is an addressable object whose
instructions a DSPy optimiser can rewrite. A string literal is not.

The instruction is deliberately non-evaluative — *"Report factual descriptions
only... Do not prescribe rewrites"* (`llm_signatures.py:43-48`).

## At the end

`v2_playbook_on_stats` drains the pool, reports losses, then closes the run
record (`llm_analyzer.py:345-363`). Draining *before* `end_run` is what makes the
run record trustworthy — it is written once every analysis it counts has landed.

`drain()` (`llm_pool.py:96-116`) works around `Queue.join()` having no timeout by
joining it through a helper thread. Workers share one deadline rather than each
getting its own, since N workers with individual grace periods would make the
real ceiling `drain_timeout + N` seconds (`llm_pool.py:111-113`).

### A caveat the captured run demonstrates

The stored run record has **`"ended_at": null`**. The run was interrupted before
`v2_playbook_on_stats` fired, so `end_run` never ran. The per-analysis rows are
all intact — they are appended as they complete — but the run-level summary
(`task_analyses`, `play_analyses`, `dropped`, `abandoned`) is absent.

A trace directory can therefore contain a run with no summary. Anything reading
`runs` should treat a null `ended_at` as "incomplete", not "zero".

## Where output lands

```
llm_analysis/                          (gitignored — .gitignore:212)
├── <timestamp>_<kind>_<n>_<name>.md   human-readable, local timestamps
└── traces/
    ├── runs/<run_id>.json             one file per run
    ├── analyses/<run_id>.jsonl        one line per analysed subject
    └── judgments/<source>.jsonl       quality labels, written out of band
```

The write path holds no database handle (`llm_trace_store.py:5-13`), so two
concurrent `ansible-playbook` runs cannot contend for a lock. DuckDB reads the
JSONL directly through `read_json_auto` globs (`llm_trace_store.py:195-231`);
the `.duckdb` file is an optional materialised view, not the system of record.
