# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Incident and remediation store for the LLM remediation pipeline.

Follows the ``llm_trace_store.py`` pattern: JSONL is the source of truth and
the DuckDB index is a materialised view, not the system of record. The index is
deliberately rebuilt in memory on each search rather than persisted, because
HNSW persistence is experimental in DuckDB and at expected volumes (tens to
hundreds of incidents) an in-memory rebuild is cheap.

Incident records carry their embedding vector and the embedding model name, so
the index rebuilds from JSONL alone and a model change is detectable per row.

Layout under the store root::

    incidents.jsonl     one record per diagnosis
    outcomes.jsonl      one record per remediation attempt
    diagnostics/<id>.json  raw gather output, kept out of the JSONL
    playbooks/pending/<id>.yml   generated, guard-passed, not yet approved
    playbooks/rejected/<id>.yml  guard-rejected, with the reason
    index/<id>.yml      successful remediations only
"""

from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

__metaclass__ = type

SCHEMA_VERSION = 1
EMBEDDING_MODEL = "embeddinggemma:latest"
SIMILARITY_THRESHOLD = 0.80
RESULT_VALUES = ("success", "failed", "unconfirmed")


class RemediationError(Exception):
    """Store or embedding failure with a message naming the broken piece."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class OllamaEmbedder:
    """Ollama /api/embed client for ``embeddinggemma:latest``."""

    def __init__(self, host: Optional[str] = None, model: str = EMBEDDING_MODEL,
                 timeout: float = 60.0):
        host = host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        if "://" not in host:
            host = "http://" + host
        self.base = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        import json as _json
        import urllib.error
        import urllib.request

        payload = _json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(
            f"{self.base}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = _json.loads(response.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise RemediationError(
                f"Ollama at {self.base} rejected the embedding request for "
                f"{self.model} (HTTP {e.code}): {detail}"
            ) from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise RemediationError(
                f"Ollama embedding service unreachable at {self.base} "
                f"(model {self.model}): {e}"
            ) from e
        embeddings = body.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise RemediationError(
                f"Ollama returned {len(embeddings or [])} embeddings for "
                f"{len(texts)} inputs (model {self.model})"
            )
        return embeddings


class RemediationStore:
    """Append-only incident store with DuckDB ``vss`` semantic search."""

    def __init__(
        self,
        root: Path,
        embedder: Optional[OllamaEmbedder] = None,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ):
        self.root = Path(root)
        self.incidents_path = self.root / "incidents.jsonl"
        self.outcomes_path = self.root / "outcomes.jsonl"
        self.diagnostics_dir = self.root / "diagnostics"
        self.pending_dir = self.root / "playbooks" / "pending"
        self.rejected_dir = self.root / "playbooks" / "rejected"
        self.index_dir = self.root / "index"
        for path in (
            self.root,
            self.diagnostics_dir,
            self.pending_dir,
            self.rejected_dir,
            self.index_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or OllamaEmbedder()
        self.similarity_threshold = similarity_threshold

    # -- records ----------------------------------------------------------

    def record_incident(
        self,
        *,
        host: str,
        summary: str,
        error_signature: str,
        service: str,
        role: str,
        severity: str,
        diagnostics: Optional[dict[str, Any]] = None,
        status: str = "open",
    ) -> str:
        """Append one incident record. Returns the incident id."""
        incident_id = f"inc-{uuid.uuid4().hex[:12]}"
        embedding = self.embedder.embed([summary])[0]
        record = {
            "incident_id": incident_id,
            "schema_version": SCHEMA_VERSION,
            "created_at": _utcnow(),
            "host": host,
            "summary": summary,
            "error_signature": error_signature,
            "service": service,
            "role": role,
            "severity": severity,
            "status": status,
            "embedding_model": self.embedder.model,
            "embedding": embedding,
        }
        self._append(self.incidents_path, record)
        if diagnostics is not None:
            (self.diagnostics_dir / f"{incident_id}.json").write_text(
                json.dumps(diagnostics, indent=2, default=str)
            )
        return incident_id

    def record_outcome(
        self,
        *,
        incident_id: str,
        playbook_path: str,
        result: str,
        confirmed_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Append one outcome record and promote the playbook on success."""
        if result not in RESULT_VALUES:
            raise RemediationError(
                f"outcome result must be one of {RESULT_VALUES}, got {result!r}"
            )
        record = {
            "incident_id": incident_id,
            "schema_version": SCHEMA_VERSION,
            "created_at": _utcnow(),
            "playbook_path": playbook_path,
            "result": result,
            "confirmed_by": confirmed_by,
        }
        self._append(self.outcomes_path, record)
        indexed = False
        if result == "success":
            self.promote(incident_id, playbook_path)
            indexed = True
        return {"incident_id": incident_id, "result": result, "indexed": indexed}

    def promote(self, incident_id: str, playbook_path: str) -> Path:
        """Copy a successful playbook into the index directory."""
        target = self.index_dir / f"{incident_id}.yml"
        shutil.copyfile(playbook_path, target)
        return target

    def remediation_for(self, incident_id: str) -> Optional[Path]:
        """Indexed playbook for an incident, if the remediation succeeded."""
        outcomes = self._read_jsonl(self.outcomes_path)
        succeeded = any(
            o.get("incident_id") == incident_id and o.get("result") == "success"
            for o in outcomes
        )
        target = self.index_dir / f"{incident_id}.yml"
        if succeeded and target.is_file():
            return target
        return None

    # -- search -----------------------------------------------------------

    def search(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        """Top-k similar incidents with cosine scores and linked remediations.

        Every incident is searchable ("have we seen this before"); the
        ``remediation_playbook`` field is set only when that incident has a
        confirmed-success remediation in the index, so only proven fixes are
        offered as remediation context. The scores come from the in-memory
        DuckDB ``vss`` HNSW index rebuilt from the JSONL records.
        """
        if not self._read_jsonl(self.incidents_path):
            return []
        query_vec = self.embedder.embed([text])[0]
        con, dim = self.rebuild_index()
        sql = (
            "SELECT incident_id, host, error_signature, summary, "
            f"array_cosine_similarity(embedding, ?::FLOAT[{dim}]) AS score "
            "FROM incidents ORDER BY score DESC LIMIT ?"
        )
        rows = con.execute(sql, [query_vec, k]).fetchall()
        con.close()
        matches = []
        for incident_id, host, signature, summary, score in rows:
            matches.append(
                {
                    "incident_id": incident_id,
                    "host": host,
                    "error_signature": signature,
                    "summary": summary,
                    "score": score,
                    "remediation_playbook": None,
                }
            )
        for match in matches:
            indexed = self.remediation_for(match["incident_id"])
            if indexed is not None:
                match["remediation_playbook"] = str(indexed)
        return matches

    def rebuild_index(self):
        """Build the in-memory DuckDB ``vss`` index from the JSONL records.

        Returns ``(connection, dimension)``. The connection owns an HNSW index
        over the embedding column; close it when done.
        """
        import duckdb

        incidents = self._read_jsonl(self.incidents_path)
        rows = [
            (
                i.get("incident_id"),
                i.get("host"),
                i.get("error_signature"),
                i.get("summary"),
                i.get("embedding_model"),
                i["embedding"],
            )
            for i in incidents
            if i.get("embedding")
        ]
        if not rows:
            raise RemediationError("no embedded incidents to index")
        dim = len(rows[0][5])
        con = duckdb.connect(":memory:")
        con.execute("INSTALL vss; LOAD vss;")
        con.execute(
            f"CREATE TABLE incidents (incident_id VARCHAR, host VARCHAR, "
            f"error_signature VARCHAR, summary VARCHAR, embedding_model VARCHAR, "
            f"embedding FLOAT[{dim}])"
        )
        con.executemany(
            "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?)", rows
        )
        con.execute(
            "CREATE INDEX incidents_hnsw ON incidents USING HNSW (embedding) "
            "WITH (metric = 'cosine')"
        )
        return con, dim

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        line = json.dumps(record, default=str) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        records = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
