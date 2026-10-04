# callback_utils

Support modules for the `llm_analyzer` callback (`plugins/callback/llm_analyzer.py`).
(The remediation action plugins and support modules have been migrated to the standalone `llmops` repository).


**These must not live in `plugins/callback/` or `plugins/action/`.** A callback plugin directory is a
plugin *namespace*, not a Python package: `PluginLoader.all()` globs `*.py` in
every configured `callback_plugins` path, imports each match, and requires it to
expose a `CallbackModule` class. Helper modules placed there are therefore
imported by Ansible at startup and then rejected, producing

    [WARNING]: Skipping plugin (.../llm_trace_store.py) as it seems to be
    invalid: module 'ansible.plugins.callback.llm_trace_store' has no
    attribute 'CallbackModule'

Worse than the noise, each helper ends up in `sys.modules` twice — once as
`ansible.plugins.callback.<name>` from Ansible's scan and once under its bare
name from the callback's own `sys.path` bootstrap — giving two distinct copies
of every class and every piece of module-level state.

The glob is not recursive and only `__init__` is a reserved basename, so no
naming convention exempts a file. Living outside the scanned path is the only
reliable fix. The action plugin loader behaves the same way: it imports every
`*.py` in `plugins/action/` and expects an `ActionModule` class.

## Modules

The callback itself keeps only what Ansible must see: the `DOCUMENTATION` block
the plugin loader parses, and the `v2_playbook_on_*` handlers that run on
Ansible's own thread. Everything reachable from a captured job lives here.

| Module | Responsibility |
| :--- | :--- |
| `llm_engine.py` | `AnsibleAnalyzer` — provider/key resolution, the DSPy programs, the startup reachability check, per-call metadata. Knows nothing about Ansible. |
| `llm_pool.py` | `AnalysisPool` — bounded queue, daemon workers, drop/block policy, timed drain. `workers=0` runs inline. |
| `llm_style.py` | Style-guide checkers. Pure functions of the YAML text, which is what lets the style pass run on a worker. |
| `llm_suggestions.py` | Maps a violation to a concrete edit. Split from the checkers so a new check does not require a new fix. |
| `llm_report.py` | Markdown renderers and the on-disk report files (local time, unlike the UTC trace store). |
| `llm_signatures.py` | DSPy signatures + `SIGNATURE_VERSION`, built lazily so importing does not import `dspy`. |
| `llm_trace_store.py` | Append-only JSONL trace store, queried with DuckDB. |
| `llm_metrics.py` | Deterministic gold labels and DSPy metrics for optimisation runs. |

Imports between these are by bare module name (`from llm_style import ...`),
because the callback primes `sys.path` with this directory rather than
importing them as a package.


