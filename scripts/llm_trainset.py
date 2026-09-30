#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a DSPy trainset from captured llm_analyzer traces, and score them.

    python scripts/llm_trainset.py stats
    python scripts/llm_trainset.py evaluate            # baseline structural score
    python scripts/llm_trainset.py backfill            # write heuristic judgments
    python scripts/llm_trainset.py examples --limit 50
    python scripts/llm_trainset.py sql "SELECT model, count(*) FROM analyses GROUP BY 1"

Gold labels are *derived from the task YAML*, not taken from the model's own
output. Labelling an example with the prediction it is meant to grade teaches an
optimiser to reproduce its current mistakes; see llm_metrics for why the
structural fields are recoverable for free.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

_UTILS_DIR = Path(__file__).resolve().parents[1] / "plugins" / "callback_utils"
if not _UTILS_DIR.is_dir():
    raise SystemExit(f"support modules not found at {_UTILS_DIR}")
sys.path.insert(0, str(_UTILS_DIR))

from llm_metrics import METRIC_VERSION, extract_gold, score_task
from llm_trace_store import TraceStore, connect

DEFAULT_ROOT = Path("llm_analysis/traces")

GOLD_FIELDS = (
    "module",
    "is_fqcn",
    "parameters",
    "idempotency",
    "conditions",
    "loop",
    "delegation",
    "privilege_escalation",
    "change_detection",
    "error_handling",
)


def _coerce(value):
    """DuckDB returns nested JSON as a string or a struct depending on shape."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}


def _fetch(root, kind="task", limit=None, require_judgment=False, min_score=1.0):
    where = ["a.error IS NULL", "a.kind = ?"]
    params = [kind]
    joins = ""
    if require_judgment:
        joins = "JOIN judgments j ON j.analysis_id = a.analysis_id"
        where.append("j.score >= ?")
        params.append(min_score)
    sql = f"""
        SELECT a.analysis_id, a.name, a.inputs, a.outputs, a.model,
               a.signature_version
        FROM analyses a {joins}
        WHERE {' AND '.join(where)}
        ORDER BY a.created_at
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    con = connect(root)
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    out = []
    for aid, name, inputs, outputs, model, sigver in rows:
        inputs, outputs = _coerce(inputs), _coerce(outputs)
        violations = inputs.get("style_violations") or []
        out.append(
            {
                "analysis_id": aid,
                "name": name,
                "task_yaml": inputs.get("source_yaml", ""),
                "style_observations": "\n".join(
                    f"- Line {v.get('line')} ({v.get('type')}): {v.get('message')}"
                    for v in violations
                ),
                "outputs": outputs,
                "model": model,
                "signature_version": sigver,
            }
        )
    return out


def build_examples(
    root=DEFAULT_ROOT,
    kind="task",
    limit=None,
    require_judgment=False,
    min_score=1.0,
    gold_source="derived",
):
    """Return ``dspy.Example`` objects carrying gold labels.

    ``gold_source="derived"`` (default) labels each example with facts parsed
    out of the task YAML. ``"captured"`` reuses the model's own output, which is
    only meaningful for inspecting what the model produced -- never for training.
    """
    import dspy

    examples = []
    for row in _fetch(root, kind, limit, require_judgment, min_score):
        payload = {
            "task_yaml": row["task_yaml"],
            "style_observations": row["style_observations"],
        }
        if gold_source == "derived":
            gold = extract_gold(row["task_yaml"])
            if gold.get("_extraction") == "unparseable":
                continue
            payload.update({k: gold[k] for k in GOLD_FIELDS if k in gold})
        else:
            payload.update(row["outputs"])
        examples.append(dspy.Example(**payload).with_inputs("task_yaml", "style_observations"))
    return examples


def cmd_evaluate(root, kind, limit):
    """Score every captured prediction against derived gold. No LM calls."""
    rows = _fetch(root, kind, limit)
    if not rows:
        sys.exit("No analyses found. Enable the callback and run a playbook first.")

    scores, per_field, skipped = [], {}, 0
    for row in rows:
        gold = extract_gold(row["task_yaml"])
        if gold.get("_extraction") == "unparseable":
            skipped += 1
            continue
        result = score_task(gold, row["outputs"])
        scores.append(result["score"])
        for name, info in result["fields"].items():
            per_field.setdefault(name, []).append(info["score"])

    if not scores:
        sys.exit(f"All {skipped} rows were unparseable.")

    print(f"metric v{METRIC_VERSION}   n={len(scores)}   skipped={skipped}")
    print(f"  mean   {statistics.mean(scores):.3f}")
    print(f"  median {statistics.median(scores):.3f}")
    print(f"  min    {min(scores):.3f}    max {max(scores):.3f}")
    print(f"  >=0.9  {sum(1 for s in scores if s >= 0.9)}/{len(scores)}")
    print("\n  per-field accuracy (worst first):")
    for name, vals in sorted(per_field.items(), key=lambda kv: statistics.mean(kv[1])):
        print(f"    {name:22} {statistics.mean(vals):.3f}")


def cmd_backfill(root, kind, limit):
    """Write a heuristic judgment row for every captured analysis.

    This is what converts a log into a trainset: after this runs,
    ``--require-judgment`` selects on a real score instead of returning almost
    nothing.
    """
    rows = _fetch(root, kind, limit)
    store = TraceStore(Path(root))
    written = 0
    for row in rows:
        gold = extract_gold(row["task_yaml"])
        if gold.get("_extraction") == "unparseable":
            continue
        result = score_task(gold, row["outputs"])
        store.record_judgment(
            analysis_id=row["analysis_id"],
            source="heuristic",
            score=result["score"],
            feedback="misses: " + (", ".join(result["misses"]) or "none"),
            metric_version=METRIC_VERSION,
        )
        written += 1
    print(f"wrote {written} heuristic judgments -> {Path(root) / 'judgments' / 'heuristic.jsonl'}")


def cmd_stats(root):
    con = connect(root)
    try:
        for label, sql in (
            ("runs", "SELECT count(*) FROM runs"),
            ("analyses", "SELECT count(*) FROM analyses"),
            ("  errored", "SELECT count(*) FROM analyses WHERE error IS NOT NULL"),
            ("  by kind", "SELECT kind, count(*) FROM analyses GROUP BY 1"),
            (
                "  by signature",
                "SELECT signature_version, count(*) FROM analyses GROUP BY 1",
            ),
            (
                "judgments",
                "SELECT source, count(*), round(avg(score),3) FROM judgments GROUP BY 1",
            ),
            (
                "  by metric",
                "SELECT metric_version, count(*), round(avg(score),3) " "FROM judgments GROUP BY 1",
            ),
        ):
            try:
                print(f"{label:15} {con.execute(sql).fetchall()}")
            except Exception as e:
                print(f"{label:15} n/a ({type(e).__name__})")
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("command", choices=["stats", "evaluate", "backfill", "examples", "sql"])
    ap.add_argument("query", nargs="?")
    ap.add_argument("--root", default=os.environ.get("LLM_TRACE_ROOT", DEFAULT_ROOT))
    ap.add_argument("--kind", default="task", choices=["task", "play"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--require-judgment", action="store_true")
    ap.add_argument("--min-score", type=float, default=1.0)
    ap.add_argument("--gold-source", default="derived", choices=["derived", "captured"])
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        sys.exit(f"No traces at {root}. Enable the callback and run a playbook first.")

    if args.command == "stats":
        return cmd_stats(root)
    if args.command == "evaluate":
        return cmd_evaluate(root, args.kind, args.limit)
    if args.command == "backfill":
        return cmd_backfill(root, args.kind, args.limit)
    if args.command == "sql":
        con = connect(root)
        try:
            for r in con.execute(args.query).fetchall():
                print(r)
        finally:
            con.close()
        return None

    examples = build_examples(
        root,
        args.kind,
        args.limit,
        args.require_judgment,
        args.min_score,
        args.gold_source,
    )
    print(f"{len(examples)} examples ({args.kind}, gold={args.gold_source})")
    if examples:
        print("inputs:", sorted(examples[0].inputs().toDict()))
        print("labels:", sorted(examples[0].labels().toDict()))
    return None


if __name__ == "__main__":
    main()
