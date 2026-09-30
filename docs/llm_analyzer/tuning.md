# Adjusting llm_analyzer

Every option is settable in `[callback_llm_analyzer]` in `ansible.cfg` or by
environment variable, and **the environment variable wins**
(`llm_analyzer.py:259` for `api_key`; the `env:`/`ini:` pairs in the
`DOCUMENTATION` block at `llm_analyzer.py:68-183` for the rest).

The full option table is in
[`plugins/callback/README.md`](../../plugins/callback/README.md). This page is
about what the settings trade against each other.

## Switching provider or model without editing config

```bash
AI_PROVIDER=gemini GEMINI_API_KEY=... AI_MODEL=gemini-1.5-pro \
  ansible-playbook playbooks/site.yml
```

Provider routing is delegated to litellm through `dspy.LM`
(`llm_engine.py:22-34`). Model strings are `<provider>/<model>`; a model that
already carries its provider prefix is passed through untouched
(`model_string`, `llm_engine.py:73-78`). This is why OpenRouter's own namespaced
slugs — `openrouter/anthropic/claude-3-opus` — work without special-casing.

Six providers resolve a key from a named variable (`llm_engine.py:27-34`):
`openai`, `openrouter`, `gemini`, `groq`, `cohere`, `anthropic`.

## The throughput settings

These four interact, and the defaults are a coherent set. Change them together.

| Option | Default | What raising it costs you |
| :--- | :--- | :--- |
| `async_workers` | `4` | Concurrent spend; provider rate limits |
| `queue_maxsize` | `64` | Memory; each entry holds the full source YAML |
| `queue_full_policy` | `block` | `block` slows the playbook; `drop` loses analyses |
| `drain_timeout` | `120.0` | Seconds of dead time at the end of a run |

### `async_workers` is a correctness setting, not a speed knob

`0` is not "the safe default" — it is the expensive one. It runs analysis inline
on Ansible's main thread (`llm_pool.py:65-69`), adding a full round trip to every
task.

Measured on the captured run, which used `async_workers = 0`: median analysis
**58.9s**, total **696s** across 11 subjects. That is 11.6 minutes added to a
playbook that otherwise does dnf and template work.

Choose `0` only when you want explanations streamed to the console in playbook
order — that is the one thing workers cannot give you, because worker output
would arrive detached from the task it describes and interleave with Ansible's
own (`llm_analyzer.py:397-405`).

### Why the queue is bounded

Tasks are enqueued far faster than a model can answer them. An unbounded queue
converts that gap into unbounded memory growth and unbounded spend
(`llm_pool.py:12-14`). Hence `block` as the default policy: it throttles the
playbook to the analysis rate and loses nothing.

Use `drop` when the playbook's own timing matters more than complete coverage.
Drops are counted, not silent — `dropped` and `abandoned` are reported at the end
of the run and written into the run record (`llm_analyzer.py:352-363`).

### `drain_timeout`

The wait at `v2_playbook_on_stats` for analyses still in flight. Too low and you
discard work you already paid for; too high and a stalled provider holds the
playbook open. With a median analysis near 60s, the 120s default absorbs roughly
two round trips per worker.

## `max_tokens` is an output cap, not a context window

This is the most commonly misread setting. Raising it does **not** let the model
read more of your playbook. It raises how much the model may *generate*, and
raises the ceiling DSPy quotes back in its truncation warning — which reports the
configured value rather than the limit an individual request actually used
(`llm_analyzer.py:114-129`).

It is the dominant cost lever, because these analyses are output-heavy. Measured
per successful subject on the captured run:

```
$ python scripts/llm_trainset.py sql \
    "SELECT kind, count(*) n, round(avg(prompt_tokens)) avg_prompt,
            round(avg(completion_tokens)) avg_completion, max(completion_tokens) max_completion
     FROM analyses WHERE error IS NULL GROUP BY 1"
('play', 1, 1196.0, 5800.0, 5800)
('task', 9, 1320.0, 7084.0, 15395)
```

A task costs about **1,320 prompt tokens and 7,084 completion tokens** — output
outweighs input roughly 5:1. If spend is the problem, `max_tokens` is the lever;
`temperature` and `provider` are not.

> **Unexplained observation.** `max_completion` for tasks is **15,395**, against a
> configured `max_tokens` of 8,192. A single response cannot exceed the cap, so
> the recorded figure must aggregate more than one model call — which is
> consistent with `get_lm_usage()` summing usage across calls
> (`llm_engine.py:229-236`), and with DSPy retrying a response its adapter failed
> to parse. **This has not been confirmed.** Treat recorded token counts as
> per-analysis totals that may cover several underlying requests, and do not use
> them to infer a single response's length.

## `temperature`

Default `0.4` (`llm_analyzer.py:108`). The task is extraction and description
against a supplied document, not generation. Lower values suit it. There is no
measurement here supporting any particular value — the captured run used the
default and nothing else was tried.

## Changing what the model is asked

The output fields are not in a prompt string. They are declared on the two
signature classes in `plugins/callback_utils/llm_signatures.py:42-127`. Adding or
changing a field means editing that file.

**If you change a signature, bump `SIGNATURE_VERSION`**
(`llm_signatures.py:19`). It is recorded on every stored trace, and without it
rows produced by two revisions pool together and any before/after comparison is
noise (`llm_signatures.py:10-13`). `stats` groups by it so a mixed store is
visible:

```
$ python scripts/llm_trainset.py stats
  by signature  [('1.0.0', 11)]
```

Note also that the scoring metric is coupled to the task signature's field
*names*: `GOLD_FIELDS` in `scripts/llm_trainset.py:36-47` and `WEIGHTS` in
`llm_metrics.py:60-71` both list them explicitly. Renaming an output field
without updating both silently drops it from scoring.

## Changing the local style checks

`plugins/callback_utils/llm_style.py` runs before the model and costs nothing.
Its findings are passed into the prompt as an input field
(`llm_signatures.py:51-54`), so adding a check changes what the model is asked to
comment on. Violations carry `type`, `message`, `line`, and optionally a
`reference` naming the source of the rule (`llm_style.py:12`).

## Turning it off

Comment out `callbacks_enabled` in `ansible.cfg`, or set it to another callback.
`CALLBACK_NEEDS_WHITELIST = True` (`llm_analyzer.py:237`) means an unlisted
plugin does nothing.

The plugin also disables *itself* whenever provider setup or validation fails,
printing the classified reason and letting the playbook continue
(`llm_analyzer.py:271-284`). A missing API key is not a broken playbook.
