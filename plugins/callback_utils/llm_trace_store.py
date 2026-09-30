# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Append-only trace store for llm_analyzer, queried with DuckDB.

Write path and query path are deliberately separate:

* The callback appends newline-delimited JSON. No database handle is held during
  a playbook run, so two concurrent ``ansible-playbook`` invocations cannot
  contend for a write lock -- DuckDB is single-writer and holds the file
  exclusively, which would make the second run fail to open it.
* DuckDB reads the JSONL directly through ``read_json_auto`` globs. Nothing has
  to be ingested before it is queryable; the ``.duckdb`` file is an optional
  materialised view, not the system of record.

Layout::

    llm_analysis/traces/
      runs/<run_id>.json           one object per playbook invocation
      analyses/<run_id>.jsonl      one object per analysed task
      judgments/<source>.jsonl     quality labels, written out of band
"""

from __future__ import absolute_import, division, print_function

import contextlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

__metaclass__ = type

SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceStore:
    """Append-only writer. Never raises into the playbook.

    Safe to call from several threads at once. ``record_analysis`` is driven by
    the async worker pool in ``llm_analyzer``, so both the sequence counter and
    the append itself are taken under one lock: a single ``write()`` of a line
    under 4 KiB would usually be atomic anyway, but an analysis row carries the
    full source YAML and routinely exceeds any such guarantee.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.runs_dir = self.root / "runs"
        self.analyses_dir = self.root / "analyses"
        self.judgments_dir = self.root / "judgments"
        for d in (self.runs_dir, self.analyses_dir, self.judgments_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.run_id: Optional[str] = None
        self._analyses_path: Optional[Path] = None
        self._seq = 0
        self._lock = threading.Lock()

    # -- run lifecycle ----------------------------------------------------

    def start_run(self, **fields: Any) -> str:
        self.run_id = uuid.uuid4().hex
        self._analyses_path = self.analyses_dir / f"{self.run_id}.jsonl"
        record = {
            "run_id": self.run_id,
            "schema_version": SCHEMA_VERSION,
            "started_at": _utcnow(),
            "ended_at": None,
            "pid": os.getpid(),
        }
        record.update(fields)
        self._write_json(self.runs_dir / f"{self.run_id}.json", record)
        return self.run_id

    def end_run(self, **fields: Any) -> None:
        if not self.run_id:
            return
        path = self.runs_dir / f"{self.run_id}.json"
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            return
        record["ended_at"] = _utcnow()
        record.update(fields)
        self._write_json(path, record)

    # -- analysis records -------------------------------------------------

    def record_analysis(
        self,
        *,
        kind: str,
        name: Optional[str],
        subject_uuid: Optional[str],
        source_yaml: str,
        style_violations: list[dict[str, Any]],
        outputs: dict[str, Any],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        signature_version: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> Optional[str]:
        """Append one analysis row. Returns its id, or None if the write failed.

        Inputs and outputs are kept in distinct top-level keys so a query can
        rebuild ``dspy.Example(**inputs, **outputs).with_inputs(*inputs)``
        without reparsing anything.
        """
        if not self.run_id or self._analyses_path is None:
            return None
        with self._lock:
            self._seq += 1
            seq = self._seq
        analysis_id = f"{self.run_id}-{seq:05d}"
        record = {
            "analysis_id": analysis_id,
            "run_id": self.run_id,
            "seq": seq,
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "name": name,
            "subject_uuid": subject_uuid,
            "created_at": _utcnow(),
            # -- inputs
            "inputs": {
                "source_yaml": source_yaml,
                "style_violations": style_violations or [],
            },
            # -- outputs
            "outputs": outputs or {},
            # -- metadata
            "model": model,
            "provider": provider,
            "signature_version": signature_version,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "error": error,
        }
        line = json.dumps(record, default=str) + "\n"
        try:
            with self._lock, open(self._analyses_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            return None
        return analysis_id

    def record_judgment(
        self,
        *,
        analysis_id: str,
        source: str,
        score: float,
        feedback: Optional[str] = None,
        metric_version: Optional[str] = None,
    ) -> None:
        """Attach a quality label to an analysis.

        Separate from the analysis record on purpose: labels arrive later than
        the prediction, may arrive more than once, and may come from a human, an
        LLM judge, or a heuristic. A column on ``analyses`` could express none of
        that without a rewrite.

        ``metric_version`` records which revision of the scoring metric produced
        the score, the way ``signature_version`` does for an analysis. Without it
        a store accumulating judgments across two metric revisions has nothing on
        disk distinguishing them. Left ``None`` for labels that no versioned
        metric produced (a human, say); rows predating the field read back as
        NULL because the views use ``union_by_name=true``.
        """
        record = {
            "analysis_id": analysis_id,
            "source": source,
            "score": score,
            "feedback": feedback,
            "metric_version": metric_version,
            "created_at": _utcnow(),
        }
        path = self.judgments_dir / f"{source}.jsonl"
        line = json.dumps(record, default=str) + "\n"
        try:
            with self._lock, open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass

    @staticmethod
    def _write_json(path: Path, record: dict[str, Any]) -> None:
        with contextlib.suppress(OSError):
            path.write_text(json.dumps(record, default=str, indent=2))


# -- query side -----------------------------------------------------------

ANALYSES_VIEW = """
CREATE OR REPLACE VIEW analyses AS
SELECT * FROM read_json_auto('{root}/analyses/*.jsonl', format='newline_delimited',
                             union_by_name=true)
"""

RUNS_VIEW = """
CREATE OR REPLACE VIEW runs AS
SELECT * FROM read_json_auto('{root}/runs/*.json', union_by_name=true)
"""

JUDGMENTS_VIEW = """
CREATE OR REPLACE VIEW judgments AS
SELECT * FROM read_json_auto('{root}/judgments/*.jsonl', format='newline_delimited',
                             union_by_name=true)
"""


def connect(root, database: str = ":memory:"):
    """Open a DuckDB connection with ``runs``/``analyses``/``judgments`` views.

    Views read the JSONL directly, so a connection opened while a playbook is
    still writing sees every record flushed so far and never blocks the writer.
    Empty directories are tolerated: the view is simply not created.
    """
    import duckdb  # imported here so the write path never needs duckdb

    root = Path(root).resolve()
    con = duckdb.connect(database)
    for sql, subdir, pattern in (
        (RUNS_VIEW, "runs", "*.json"),
        (ANALYSES_VIEW, "analyses", "*.jsonl"),
        (JUDGMENTS_VIEW, "judgments", "*.jsonl"),
    ):
        if any((root / subdir).glob(pattern)):
            con.execute(sql.format(root=root.as_posix()))
    return con
