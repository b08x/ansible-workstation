# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Controller-side CLI for the LLM remediation pipeline.

Runs in the repo ``.venv`` interpreter as a child of the action plugins, which
import only the standard library. Reads one JSON document on stdin and writes
one JSON document on stdout; a non-zero exit means the caller's action plugin
must fail with the child's stderr as the message.

Subcommands::

    diagnose  gather JSON  -> incident + matches + pending playbook path
    verify   gather JSON + old signature -> resolved flag + new signature
    record   outcome       -> written outcome, indexed on success

Provider configuration is the same one ``llm_analyzer`` uses: the
``[callback_llm_analyzer]`` section of ``ansible.cfg``, overridden by the
``AI_PROVIDER`` / ``AI_MODEL`` / ``AI_TEMPERATURE`` / ``AI_MAX_TOKENS`` and
per-provider ``*_API_KEY`` environment variables.
"""

from __future__ import absolute_import, division, print_function

import argparse
import configparser
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from remediation_bridge import PROGRESS_PREFIX

__metaclass__ = type

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = Path(
    os.environ.get(
        "REMEDIATION_STORE",
        os.path.expanduser("~/.local/share/syncopated/remediation/"),
    )
)
EXIT_USAGE = 2
EXIT_PROVIDER = 3
EXIT_OLLAMA = 4
EXIT_INTERNAL = 5
LINT_TIMEOUT = 180


def _progress(text: str, event: str = "info", seconds: float | None = None) -> None:
    """One progress event on stderr; the action plugin displays it immediately.

    ``event`` is one of start, done, failed, rejected, info.
    """
    record = {"event": event, "text": text}
    if seconds is not None:
        record["seconds"] = round(seconds, 1)
    print(f"{PROGRESS_PREFIX}{json.dumps(record)}", file=sys.stderr, flush=True)


class _Stage:
    """Announce a stage, then report how long it took when it ends."""

    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        _progress(self.message, "start")
        self.started = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        seconds = time.monotonic() - self.started
        _progress(self.message, "failed" if exc_type else "done", seconds)
        return False


def _fail(code: int, message: str) -> int:
    print(message, file=sys.stderr)
    return code


def _read_payload() -> dict:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"stdin is not valid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise ValueError("stdin payload must be a JSON object")
    return payload


def _load_provider_config() -> dict:
    """[callback_llm_analyzer] from ansible.cfg, with env overrides."""
    from llm_engine import PROVIDER_ENV_VARS

    config = {
        "provider": "openrouter",
        "model": "openrouter/deepseek/deepseek-v4-flash",
        "temperature": 0.4,
        "max_tokens": 8192,
        "api_key": None,
    }
    parser = configparser.ConfigParser()
    cfg = Path(os.environ.get("ANSIBLE_CONFIG") or REPO_ROOT / "ansible.cfg")
    if cfg.is_file():
        parser.read(cfg)
        section = "callback_llm_analyzer"
        if parser.has_section(section):
            for key in ("provider", "model", "api_key"):
                if parser.has_option(section, key):
                    config[key] = parser.get(section, key)
            for key, cast in (("temperature", float), ("max_tokens", int)):
                if parser.has_option(section, key):
                    try:
                        config[key] = cast(parser.get(section, key))
                    except ValueError:
                        pass
    for env, key, cast in (
        ("AI_PROVIDER", "provider", str),
        ("AI_MODEL", "model", str),
        ("AI_TEMPERATURE", "temperature", float),
        ("AI_MAX_TOKENS", "max_tokens", int),
    ):
        if os.environ.get(env):
            try:
                config[key] = cast(os.environ[env])
            except ValueError:
                pass
    env_var = PROVIDER_ENV_VARS.get(str(config["provider"]).lower())
    if env_var and os.environ.get(env_var):
        config["api_key"] = os.environ[env_var]
    return config


def _analyzer():
    """Build and validate the LLM analyzer, or exit with a clear message."""
    from llm_engine import AnsibleAnalyzer

    config = _load_provider_config()
    analyzer = AnsibleAnalyzer(
        provider=str(config["provider"]),
        api_key=str(config["api_key"] or ""),
        model=str(config["model"]),
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )
    analyzer.setup()
    reason = analyzer.validate()
    if reason:
        raise ProviderError(
            f"LLM provider {analyzer.provider} [{analyzer.model_string}] is not "
            f"usable: {reason}"
        )
    return analyzer


class ProviderError(Exception):
    """The configured LLM provider is unreachable or rejects requests."""


def _store():
    from remediation_store import OllamaEmbedder, RemediationStore

    threshold = float(os.environ.get("REMEDIATION_SIMILARITY_THRESHOLD", "0.80"))
    return RemediationStore(DEFAULT_STORE, OllamaEmbedder(), threshold)


def _tool(name: str, fallback_neighbor: str) -> str:
    """Locate an Ansible tool, preferring the venv this CLI runs in."""
    override = os.environ.get(f"REMEDIATION_{name.upper().replace('-', '_')}")
    if override:
        return override
    found = shutil.which(name)
    if found:
        return found
    neighbor = Path(sys.executable).parent / fallback_neighbor
    if neighbor.is_file():
        return str(neighbor)
    raise RuntimeError(f"cannot find {name}; set REMEDIATION_{name.upper().replace('-', '_')}")


def _strip_code_fence(text: str) -> str:
    """Remove a markdown code fence a model habitually wraps YAML in."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _run_guards(store, incident_id: str, playbook_yaml: str) -> tuple[str, list[str]]:
    """YAML parse, volume scan, syntax-check, ansible-lint. Returns verdict."""
    from remediation_guard import scan_outage, scan_playbook

    if not playbook_yaml.strip():
        return "rejected", ["generated playbook is empty"]

    _progress("checking the draft for volume removal and unproven container removal")
    try:
        violations = scan_playbook(playbook_yaml)
        outages = scan_outage(playbook_yaml)
    except ValueError as e:
        _progress(str(e), "rejected")
        return "rejected", [str(e)]
    if violations:
        _progress(f"volume guard: {violations[0]}", "rejected")
        return "rejected", violations
    if outages:
        _progress(f"outage guard: {outages[0]}", "rejected")
        return "rejected", outages

    pending = store.pending_dir / f"{incident_id}.yml"
    pending.write_text(playbook_yaml.rstrip("\n") + "\n")
    try:
        with _Stage("ansible-playbook --syntax-check"):
            syntax = subprocess.run(
                [_tool("ansible-playbook", "ansible-playbook"), "--syntax-check", str(pending)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                timeout=60,
            )
        if syntax.returncode != 0:
            pending.unlink(missing_ok=True)
            _progress("syntax-check failed", "rejected")
            return "rejected", [
                "ansible-playbook --syntax-check failed: "
                f"{(syntax.stderr or syntax.stdout).strip()[:500]}"
            ]
        with _Stage("ansible-lint --profile production"):
            lint = subprocess.run(
                [_tool("ansible-lint", "ansible-lint"), "--profile", "production", "--nocolor", str(pending)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                timeout=LINT_TIMEOUT,
            )
        if lint.returncode != 0:
            pending.unlink(missing_ok=True)
            _progress("ansible-lint failed", "rejected")
            return "rejected", [
                f"ansible-lint --profile production failed: "
                f"{(lint.stdout or lint.stderr).strip()[:800]}"
            ]
    except (subprocess.TimeoutExpired, OSError, RuntimeError) as e:
        pending.unlink(missing_ok=True)
        _progress(f"guard tool failure: {e}", "rejected")
        return "rejected", [f"guard tool failure: {e}"]

    _progress("draft passed every guard; ready for review", "done")
    return "generated", []


def _health_check(value) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value or {})


def cmd_diagnose(payload: dict) -> int:
    import dspy
    from remediation_signatures import (
        PLAYBOOK_SKELETON,
        SIGNATURE_VERSION,
        build,
        trim_diagnostics,
    )
    from remediation_templates import match_template

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return _fail(EXIT_USAGE, "diagnose requires a 'diagnostics' object")
    from remediation_health import split_history

    host = str(payload.get("host") or "unknown")
    store = _store()

    try:
        analyzer = _analyzer()
    except ProviderError as e:
        return _fail(EXIT_PROVIDER, str(e))
    except Exception as e:  # noqa: BLE001 - surfaced verbatim to the operator
        return _fail(EXIT_PROVIDER, f"LLM provider setup failed: {e}")

    budget = int(os.environ.get("REMEDIATION_CONTEXT_BUDGET", "24000"))
    # The model sees older journal entries as history, not as live faults.
    trimmed = trim_diagnostics(split_history(diagnostics), char_budget=budget)
    diagnose_sig, generate_sig = build()

    try:
        with _Stage(f"diagnosing with {analyzer.model_string}"), dspy.context(lm=analyzer.lm):
            prediction = dspy.Predict(diagnose_sig)(
                diagnostics_json=json.dumps(trimmed, default=str)
            )
    except Exception as e:  # noqa: BLE001 - provider errors must fail loudly
        return _fail(EXIT_PROVIDER, f"LLM diagnosis call failed: {e}")

    summary = str(prediction.summary).strip()
    error_signature = str(prediction.error_signature).strip().lower()
    _progress(
        f"diagnosis: {error_signature}, service {prediction.service}, "
        f"severity {prediction.severity}"
    )
    try:
        _progress("recording the incident and embedding its summary")
        incident_id = store.record_incident(
            host=host,
            summary=summary,
            error_signature=error_signature,
            service=str(prediction.service),
            role=str(prediction.role),
            severity=str(prediction.severity),
            diagnostics=diagnostics,
        )
    except Exception as e:  # noqa: BLE001 - RemediationError names the service
        return _fail(EXIT_OLLAMA, str(e))

    try:
        matches = store.search(summary, k=5)
    except Exception as e:  # noqa: BLE001
        return _fail(EXIT_OLLAMA, f"semantic search failed: {e}")
    # The incident recorded above is itself the closest match; it carries no
    # remediation and must not be offered as context for its own generation.
    matches = [m for m in matches if m["incident_id"] != incident_id]
    best = f", best score {matches[0]['score']:.2f}" if matches else ""
    _progress(f"incident {incident_id}: {len(matches)} similar past incidents{best}")

    similar = []
    for match in matches:
        if match["score"] < store.similarity_threshold:
            continue
        playbook_path = match.get("remediation_playbook")
        if not playbook_path:
            continue
        similar.append(
            {
                "incident_id": match["incident_id"],
                "host": match["host"],
                "error_signature": match["error_signature"],
                "summary": match["summary"],
                "score": match["score"],
                "playbook_yaml": Path(playbook_path).read_text(),
            }
        )

    role = str(prediction.role)
    role_context = f"Affected role: {role}"
    role_dir = REPO_ROOT / "roles" / role
    if role_dir.is_dir():
        role_context += (
            f"; role code lives in {role_dir} and its tasks run podman "
            "rootless (become: false) under the user account"
        )

    template = match_template(
        error_signature=error_signature,
        service=str(prediction.service),
        role=role,
    )
    if template is not None:
        _progress(f"known failure: using template {template['template_id']}, no model call")
        # Tier 1: the playbook is a hand-authored template for a known error
        # signature. No model drafted this text, but the guards below still
        # validate it like any other playbook.
        tier = "template"
        playbook_yaml = template["playbook_yaml"]
        rationale = template["rationale"]
        health_check = dict(template["health_check"])
    else:
        # Tier 2: freeform generation, seeded with the lint-clean skeleton.
        _progress(
            f"no template matches; drafting a playbook with the model, "
            f"{len(similar)} past remediations as reference"
        )
        try:
            with _Stage("drafting"), dspy.context(lm=analyzer.lm):
                generated = dspy.Predict(generate_sig)(
                    summary=summary,
                    diagnostics_json=json.dumps(trimmed, default=str),
                    similar_incidents=json.dumps(similar, default=str),
                    role_context=role_context,
                    playbook_skeleton=PLAYBOOK_SKELETON,
                )
        except Exception as e:  # noqa: BLE001
            return _fail(EXIT_PROVIDER, f"LLM remediation generation failed: {e}")
        tier = "llm"
        playbook_yaml = _strip_code_fence(str(generated.playbook_yaml))
        rationale = str(generated.rationale)
        health_check = _health_check(generated.health_check)

    verdict, reasons = _run_guards(store, incident_id, playbook_yaml)

    output = {
        "incident_id": incident_id,
        "tier": tier,
        "signature_version": SIGNATURE_VERSION,
        "template_id": template["template_id"] if template else None,
        "template_version": template["template_version"] if template else None,
        "summary": summary,
        "error_signature": error_signature,
        "service": str(prediction.service),
        "role": role,
        "severity": str(prediction.severity),
        "matches": matches,
        "status": verdict,
        "rationale": rationale,
        "health_check": health_check,
    }
    if verdict == "rejected":
        rejected = store.rejected_dir / f"{incident_id}.yml"
        if rejected.parent.is_dir():
            rejected.write_text(playbook_yaml)
        (store.rejected_dir / f"{incident_id}.reason.json").write_text(
            json.dumps({"reasons": reasons}, indent=2)
        )
        output["rejected_reasons"] = reasons
        output["playbook_path"] = str(rejected)
    else:
        output["playbook_path"] = str(store.pending_dir / f"{incident_id}.yml")
        output["playbook_yaml"] = playbook_yaml
    print(json.dumps(output, default=str))
    return 0


def cmd_verify(payload: dict) -> int:
    import dspy
    from remediation_signatures import build, trim_diagnostics

    diagnostics = payload.get("diagnostics")
    old_signature = str(payload.get("error_signature") or "").strip().lower()
    if not isinstance(diagnostics, dict) or not old_signature:
        return _fail(EXIT_USAGE, "verify requires 'diagnostics' and 'error_signature'")

    try:
        analyzer = _analyzer()
    except ProviderError as e:
        return _fail(EXIT_PROVIDER, str(e))
    except Exception as e:  # noqa: BLE001
        return _fail(EXIT_PROVIDER, f"LLM provider setup failed: {e}")

    trimmed = trim_diagnostics(diagnostics)
    diagnose_sig, _ = build()
    try:
        with _Stage(f"re-diagnosing with {analyzer.model_string}"), dspy.context(lm=analyzer.lm):
            prediction = dspy.Predict(diagnose_sig)(
                diagnostics_json=json.dumps(trimmed, default=str)
            )
    except Exception as e:  # noqa: BLE001
        return _fail(EXIT_PROVIDER, f"LLM verification call failed: {e}")

    new_signature = str(prediction.error_signature).strip().lower()
    resolved = bool(new_signature) and new_signature != old_signature
    print(
        json.dumps(
            {
                "resolved": resolved,
                "new_signature": new_signature,
                "old_signature": old_signature,
                "summary": str(prediction.summary).strip(),
            }
        )
    )
    return 0


def cmd_record(payload: dict) -> int:
    incident_id = payload.get("incident_id")
    result = payload.get("result")
    playbook_path = payload.get("playbook_path")
    if not incident_id or not playbook_path or not result:
        return _fail(
            EXIT_USAGE,
            "record requires 'incident_id', 'playbook_path' and 'result'",
        )
    from remediation_store import RESULT_VALUES

    if result not in RESULT_VALUES:
        return _fail(EXIT_USAGE, f"record result must be one of {RESULT_VALUES}, got {result!r}")
    store = _store()
    _progress(f"recording outcome {result} for {incident_id}")
    try:
        outcome = store.record_outcome(
            incident_id=str(incident_id),
            playbook_path=str(playbook_path),
            result=str(result),
            confirmed_by=payload.get("confirmed_by"),
        )
    except Exception as e:  # noqa: BLE001
        return _fail(EXIT_INTERNAL, f"recording outcome failed: {e}")
    print(json.dumps(outcome))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("subcommand", choices=["diagnose", "verify", "record"])
    args = parser.parse_args(argv)
    try:
        payload = _read_payload()
    except ValueError as e:
        return _fail(EXIT_USAGE, str(e))
    return {"diagnose": cmd_diagnose, "verify": cmd_verify, "record": cmd_record}[args.subcommand](
        payload
    )


if __name__ == "__main__":
    sys.exit(main())
