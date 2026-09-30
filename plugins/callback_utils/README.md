# callback_utils

Support modules for two consumers: the `llm_analyzer` callback
(`plugins/callback/llm_analyzer.py`) and the remediation action plugins
(`plugins/action/remediation_*.py`, documented in
[`../action/README.md`](../action/README.md)).

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

## Remediation modules

These split along one line: which Python interpreter imports them. The action
plugins run inside `ansible-playbook`, which cannot import `dspy` or `duckdb`.
Modules the action plugins import therefore use only the standard library.
Everything that needs `dspy`, `duckdb` or Ollama runs in a child process,
`.venv/bin/python remediation_cli.py`, which exchanges one JSON document on
stdin and one on stdout.

| Module | Interpreter | Responsibility |
| :--- | :--- | :--- |
| `remediation_bridge.py` | `ansible-playbook` | Starts the CLI child, feeds stdin and drains stdout on threads, streams `REMEDIATION_PROGRESS` events from stderr, returns the parsed result or a `failed` result. |
| `remediation_health.py` | both | `assess`: the healthy-host gate, from container and pod state only. `split_history`: moves journal entries older than the latest container start to `*_history` keys. |
| `remediation_style.py` | `ansible-playbook` | Renders one progress event as a styled line (Charm palette, 24-bit colour) or as plain ASCII words. `color_enabled` honours `NO_COLOR`, Ansible colour and whether stdout is a terminal. |
| `remediation_cli.py` | `.venv` | Subcommands `diagnose`, `verify` and `record`. Provider setup, both model calls, store access, guard runs, progress events. |
| `remediation_signatures.py` | `.venv` | `DiagnoseIncident` and `GenerateRemediation` DSPy signatures, `SIGNATURE_VERSION`, the playbook skeleton, and `trim_diagnostics`. `dspy` is imported only inside `build()`. |
| `remediation_store.py` | `.venv` | JSONL incidents and outcomes, Ollama `/api/embed` embeddings, in-memory DuckDB `vss` HNSW search, promotion into `index/`. |
| `remediation_guard.py` | `.venv` | `scan_playbook`, the volume guard, and `scan_outage`, the prove-before-remove guard. Pure functions of the YAML text. |
| `remediation_templates.py` | `.venv` | Hand-written remediations keyed on signature, service and role. |

The CLI imports these by bare module name, like the callback modules above,
because Python puts the script's own directory on `sys.path`.
