# llm_analyzer

A notification callback that narrates an Ansible run. As each play and task is
dispatched, it sends the source YAML to a language model and writes back a
structured explanation — what the task is trying to achieve, which module it
uses, every parameter, and whether repeated runs are safe.

It also keeps every prediction it ever made, which is the part that turns a
commentary feature into something you can measure and improve.

| Document | What it covers |
| :--- | :--- |
| [how-it-works.md](how-it-works.md) | Plain-language walkthrough of the run path, in the order events actually happen |
| [tuning.md](tuning.md) | Every knob, what it trades against what, and the two that are routinely misread |
| [use-cases.md](use-cases.md) | What the captured output is good for — each one marked verified or not |

## Scope of these documents

This is the explanatory layer. The per-option reference tables live in
[`plugins/callback/README.md`](../../plugins/callback/README.md), and the module
map and the reason the helpers sit outside the plugin directory live in
[`plugins/callback_utils/README.md`](../../plugins/callback_utils/README.md).
Those are not repeated here.

## Evidence and citation policy

Every behavioural claim below cites either a source location (`file:line`) or a
command that was actually run. Where a claim comes from executing something, the
real output is shown.

Measurements come from one captured run, `2ab5a61b`, recorded 2026-09-10 against
`openrouter/ibm-granite/granite-4.2-8b` at `temperature 0.4`, `max_tokens 8192`,
`async_workers 0`, signature version `1.0.0`
(`llm_analysis/traces/runs/2ab5a61be3c54b4bac7b175dda1db34d.json`). It covers
11 subjects: 1 play and 10 tasks.

**One run on one model is a sample of one.** The numbers here are real and
reproducible against that stored trace, but they characterise that model on that
playbook. Nothing here establishes what a different model would score, and
per-field accuracies computed over 9 rows have wide error bars regardless of how
precisely they print.

Where a capability is implemented but was not exercised, it is marked
**Supported by code, not executed** rather than described as if it had been
tested.
