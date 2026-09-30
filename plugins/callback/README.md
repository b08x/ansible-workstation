# callback

Repo-local callback plugins, loaded via `callback_plugins = ./plugins/callback`
in `ansible.cfg`.

| Plugin | Type | Purpose |
| :--- | :--- | :--- |
| `llm_analyzer.py` | notification | Explains every play and task with an LLM, off Ansible's main thread, and records each prediction for later optimisation. |

Support modules live in [`../callback_utils/`](../callback_utils/README.md) —
not here. That README explains why: Ansible globs `*.py` in this directory and
rejects anything without a `CallbackModule`, so a helper placed here is imported
twice under two names. Only `*.py` files that *are* callback plugins belong in
this directory.

## llm_analyzer

### Enable

Already enabled in this repo's `ansible.cfg`:

```ini
[defaults]
callbacks_enabled = llm_analyzer

[callback_llm_analyzer]
provider = openrouter
model = openrouter/deepseek/deepseek-v4-flash
temperature = 0.4
max_tokens = 8192
```

The plugin disables itself and lets the playbook continue if the provider fails
to initialise or the API key does not validate — it never fails a run.

### Configuration

Every option is settable in the `[callback_llm_analyzer]` section of
`ansible.cfg` or by environment variable. The environment variable wins.

| Option | Env | Default | Notes |
| :--- | :--- | :--- | :--- |
| `provider` | `AI_PROVIDER` | `openai` | `openai`, `gemini`, `groq`, `openrouter`, `cohere`, `anthropic` |
| `api_key` | `<PROVIDER>_API_KEY` | — | e.g. `OPENROUTER_API_KEY`. The provider-specific variable takes precedence over `api_key` in `ansible.cfg`. |
| `model` | `AI_MODEL` | `gpt-4` | |
| `temperature` | `AI_TEMPERATURE` | `0.4` | |
| `max_tokens` | `AI_MAX_TOKENS` | `1000` | Output budget per response, **not** a context window — see below. |
| `async_workers` | `AI_ASYNC_WORKERS` | `4` | `0` runs inline and streams to the console. |
| `queue_maxsize` | `AI_QUEUE_MAXSIZE` | `64` | Pending analyses held in memory. |
| `queue_full_policy` | `AI_QUEUE_FULL_POLICY` | `block` | `block` throttles the playbook; `drop` never delays it and counts losses. |
| `drain_timeout` | `AI_DRAIN_TIMEOUT` | `120.0` | Seconds to wait for pending analyses at `v2_playbook_on_stats`. |

Run against a different provider without touching `ansible.cfg`:

```bash
AI_PROVIDER=gemini GEMINI_API_KEY=... AI_MODEL=gemini-1.5-pro \
  ansible-playbook playbooks/site.yml
```

#### Two settings that are easy to get wrong

**`max_tokens` is an output cap.** Setting it to the model's context length does
not buy longer analyses. It only raises the ceiling DSPy quotes back in its
truncation warning, which reports this configured value rather than the limit an
individual request actually used.

**`async_workers` is not just a speed knob.** Ansible calls
`v2_playbook_on_task_start` on its main thread and waits for it to return before
dispatching the task, so `async_workers = 0` adds a full LLM round trip to
*every task in the playbook*. With workers, the handler only serialises the task
and enqueues it. Use `0` when you want explanations streamed to the console in
playbook order; otherwise leave it at the default and read the files.

The queue bound is deliberate: tasks are enqueued far faster than an LLM can
answer them, so an unbounded queue turns a fast playbook into unbounded memory
growth and unbounded spend.

### Output

Written under `llm_analysis/` in the directory the playbook ran from:

```
llm_analysis/
├── <kind>_<count>_<name>.md     rendered analysis + style-violation section
└── traces/
    ├── runs/<run_id>.json       one file per playbook run
    ├── analyses/<run_id>.jsonl  one record per analysed play or task
    └── judgments/<source>.jsonl quality labels, written out of band
```

The run file is created at the start of the run and rewritten once the pool has
drained, so the counts it ends up carrying (including `dropped` and
`abandoned`) describe analyses that actually landed.

### Scoring and optimisation

`scripts/llm_trainset.py` turns captured traces into a DSPy trainset and scores
them, so the engine can be exercised without running a playbook:

```bash
python scripts/llm_trainset.py stats
python scripts/llm_trainset.py evaluate              # baseline structural score
python scripts/llm_trainset.py backfill              # write heuristic judgments
python scripts/llm_trainset.py examples --limit 50
python scripts/llm_trainset.py sql "SELECT model, count(*) FROM analyses GROUP BY 1"
```

The trace root defaults to the store above and is overridable with `--root` or
`LLM_TRACE_ROOT`. `--kind` selects `task` (default) or `play`; `evaluate` also
takes `--require-judgment`, `--min-score` and `--gold-source`.

Gold labels default to `derived` — computed from the task YAML rather than taken
from the model's own output. Labelling an example with the prediction it is
meant to grade teaches an optimiser to reproduce its current mistakes.

### Internals

See [`../callback_utils/README.md`](../callback_utils/README.md) for the module
map. The short version: `v2_playbook_on_*` runs on Ansible's thread and does
only what needs the live object — serialising it, because Ansible mutates and
reuses `Task` objects as the play advances. Style checking, the LLM round trip,
and trace and markdown writing are pure functions of that captured text and run
on the pool.
