"""fact-5, fact-6, fact-7, fact-13, fact-14: the remediation store."""

from __future__ import absolute_import, division, print_function

import json

import pytest

from remediation_store import (
    OllamaEmbedder,
    RemediationError,
    RemediationStore,
)

SUMMARY_A = (
    "podman langfuse pod degraded container state improper shm tmpfs mount "
    "einval invalid argument error"
)
SUMMARY_B_QUERY = (
    "podman pod degraded container state improper shm tmpfs mount einval "
    "invalid argument error on langfuse"
)
PLAYBOOK = "---\n- name: Fix\n  hosts: all\n  tasks: []\n"


def _store(tmp_path, stub_embedder):
    return RemediationStore(tmp_path / "store", stub_embedder)


def _record(store, host="tinybot", summary=SUMMARY_A, signature="podman:shm_einval"):
    return store.record_incident(
        host=host,
        summary=summary,
        error_signature=signature,
        service="langfuse",
        role="llmops.langfuse",
        severity="high",
        diagnostics={"host": {"ok": True, "data": {}, "error": None}},
    )


# fact-5
def test_incident_appended_to_jsonl_on_controller(tmp_path, stub_embedder):
    store = _store(tmp_path, stub_embedder)
    incident_id = _record(store)
    lines = (tmp_path / "store" / "incidents.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["incident_id"] == incident_id
    assert record["host"] == "tinybot"
    assert record["embedding_model"] == "stub-embed"
    assert record["embedding"]
    assert (tmp_path / "store" / "diagnostics" / f"{incident_id}.json").is_file()


# fact-6
def test_rebuild_index_uses_duckdb_vss_hnsw(tmp_path, stub_embedder):
    store = _store(tmp_path, stub_embedder)
    _record(store)
    con, dim = store.rebuild_index()
    indexes = con.execute(
        "SELECT index_name, table_name FROM duckdb_indexes() WHERE table_name = 'incidents'"
    ).fetchall()
    assert ("incidents_hnsw", "incidents") in indexes
    data_type = con.execute(
        "SELECT data_type FROM duckdb_columns() "
        "WHERE table_name = 'incidents' AND column_name = 'embedding'"
    ).fetchone()[0]
    assert data_type == f"FLOAT[{dim}]"
    con.close()


# fact-13
@pytest.mark.parametrize("result", ["failed", "unconfirmed"])
def test_failed_and_unconfirmed_not_indexed(tmp_path, stub_embedder, result):
    store = _store(tmp_path, stub_embedder)
    incident_id = _record(store)
    store.record_outcome(
        incident_id=incident_id, playbook_path=_write_pending(store, incident_id),
        result=result,
    )
    assert store.remediation_for(incident_id) is None
    assert list((tmp_path / "store" / "index").iterdir()) == []


def test_success_promotes_into_index(tmp_path, stub_embedder):
    store = _store(tmp_path, stub_embedder)
    incident_id = _record(store)
    pending = _write_pending(store, incident_id)
    outcome = store.record_outcome(
        incident_id=incident_id, playbook_path=str(pending), result="success"
    )
    assert outcome["indexed"] is True
    assert store.remediation_for(incident_id) == (
        tmp_path / "store" / "index" / f"{incident_id}.yml"
    )
    assert store.remediation_for(incident_id).read_text() == PLAYBOOK


def _write_pending(store, incident_id):
    pending = store.pending_dir / f"{incident_id}.yml"
    pending.write_text(PLAYBOOK)
    return pending


# fact-7
def test_search_returns_matches_with_scores_and_remediations(tmp_path, stub_embedder):
    store = _store(tmp_path, stub_embedder)
    promoted_id = _record(store, host="tinybot")
    pending = _write_pending(store, promoted_id)
    store.record_outcome(
        incident_id=promoted_id, playbook_path=str(pending), result="success"
    )
    other_id = _record(store, host="gir", summary="unrelated kernel panic oom", signature="kernel:oom")
    store.record_outcome(
        incident_id=other_id,
        playbook_path=str(_write_pending(store, other_id)),
        result="failed",
    )

    matches = store.search(SUMMARY_B_QUERY, k=5)
    assert matches, "expected at least one match"
    top = matches[0]
    assert top["incident_id"] == promoted_id
    assert top["score"] > 0.5
    assert top["remediation_playbook"] == str(
        tmp_path / "store" / "index" / f"{promoted_id}.yml"
    )
    # The failed incident is searchable as context but carries no remediation.
    by_id = {m["incident_id"]: m for m in matches}
    assert by_id[other_id]["remediation_playbook"] is None


# fact-14
def test_host_b_query_returns_host_a_remediation(tmp_path, stub_embedder):
    store_a = _store(tmp_path, stub_embedder)
    incident_id = _record(store_a, host="tinybot")
    pending = _write_pending(store_a, incident_id)
    store_a.record_outcome(
        incident_id=incident_id, playbook_path=str(pending), result="success"
    )

    store_b = RemediationStore(tmp_path / "store", stub_embedder)
    matches = store_b.search(SUMMARY_B_QUERY, k=5)
    top = matches[0]
    assert top["host"] == "tinybot"
    assert top["score"] >= store_b.similarity_threshold
    assert top["remediation_playbook"] is not None
    assert store_b.remediation_for(top["incident_id"]).read_text() == PLAYBOOK


def test_invalid_result_rejected(tmp_path, stub_embedder):
    store = _store(tmp_path, stub_embedder)
    incident_id = _record(store)
    with pytest.raises(RemediationError):
        store.record_outcome(
            incident_id=incident_id,
            playbook_path=str(_write_pending(store, incident_id)),
            result="bogus",
        )


# fact-17 (ollama half)
def test_unreachable_ollama_names_the_service():
    embedder = OllamaEmbedder(host="http://127.0.0.1:9")
    with pytest.raises(RemediationError) as excinfo:
        embedder.embed(["probe"])
    assert "Ollama" in str(excinfo.value)
    assert "127.0.0.1:9" in str(excinfo.value)


@pytest.mark.ollama
def test_real_ollama_embeddinggemma(tmp_path):
    import json as _json
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            models = [m["name"] for m in _json.loads(r.read())["models"]]
    except OSError:
        pytest.skip("no local Ollama daemon")
    if not any(m.startswith("embeddinggemma") for m in models):
        pytest.skip("embeddinggemma:latest not pulled")

    store = RemediationStore(tmp_path / "store", OllamaEmbedder())
    incident_id = _record(store)
    matches = store.search(SUMMARY_B_QUERY, k=5)
    assert matches[0]["incident_id"] == incident_id
