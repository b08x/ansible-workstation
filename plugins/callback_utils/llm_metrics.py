# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Deterministic gold labels and DSPy metrics for Ansible task analysis.

The problem this solves
-----------------------
Every DSPy optimiser takes ``metric`` as its first argument and invokes it as
``metric(gold, pred, trace)`` -- it needs a *gold* example, not just a
prediction. Captured traces are predictions with no gold, so a log of them
cannot be optimised against. Human labelling is the obvious answer and does not
scale: 22 captured traces produced exactly one human judgment.

The way out is domain-specific. An Ansible task is not free-form text: it is a
structured document, and most of what the analyser is asked to report is
*recoverable from the source YAML by parsing it*. The module name, whether it is
fully qualified, the parameter names, and the presence of ``when`` / ``loop`` /
``become`` / ``register`` / ``delegate_to`` / ``ignore_errors`` are all facts, not
opinions. Ansible's own ``ModuleArgsParser`` recovers them exactly -- including
``k=v`` shorthand and the ``args:`` block, which are painful to parse by hand.

So gold comes for free for 10 of the 13 output fields, at zero cost and zero
latency.

What this is NOT
----------------
This is a **proxy metric**. It measures whether the model is *grounded in the
task it was given*, not whether its prose is good. ``goal``, ``role_in_play`` and
``idempotency_mechanism`` are the fields with actual value-add and none of them
are checked here. A model could score 1.0 structurally and still write vacuous
prose -- the classic Goodhart failure.

It is still the right metric to start with: a model that misreports the module
name or invents parameters is definitely wrong, and cheap-and-certain beats
expensive-and-noisy as a first optimisation signal. Pair it with
:func:`judge_metric` once structural scores plateau, and keep the two scores in
separate ``judgments`` sources so their disagreement stays visible.
"""

from __future__ import absolute_import, division, print_function

import re
from typing import Any, Optional

import yaml

__metaclass__ = type

METRIC_VERSION = "1.0.0"

_LOADER_READY = False

#: Modules that are inherently non-idempotent unless guarded.
_UNGUARDED = {"command", "shell", "raw", "script"}

#: Guards that make an otherwise non-idempotent module idempotent.
_GUARD_ARGS = {"creates", "removes"}

#: Field weights. They sum to 1.0. ``module`` and ``parameters`` dominate
#: because getting either wrong means the analysis is about a different task.
WEIGHTS = {
    "module": 0.25,
    "parameters": 0.20,
    "idempotency": 0.15,
    "is_fqcn": 0.10,
    "conditions": 0.05,
    "loop": 0.05,
    "delegation": 0.05,
    "privilege_escalation": 0.05,
    "change_detection": 0.05,
    "error_handling": 0.05,
}

#: Fields whose gold is only presence/absence; the model writes prose, so they
#: are scored on whether it correctly reported *something* vs *nothing*.
_PRESENCE_FIELDS = (
    "conditions",
    "loop",
    "delegation",
    "privilege_escalation",
    "change_detection",
    "error_handling",
)

_ABSENT_RE = re.compile(
    r"^\s*(none|n/?a|default|not\s+(set|used|handled|applicable)|no|false|-{1,2}|)\s*\.?\s*$",
    re.I,
)


def _ensure_loader() -> None:
    """Initialise Ansible's plugin loader once.

    ``ModuleArgsParser`` resolves the action through the module loader, which
    raises ``couldn't resolve module/action`` for any FQCN until the collection
    finder is installed. Callers outside a playbook run must do this explicitly.
    """
    global _LOADER_READY
    if _LOADER_READY:
        return
    try:
        from ansible.plugins.loader import init_plugin_loader

        init_plugin_loader()
    except Exception:
        pass
    _LOADER_READY = True


def _task_keywords() -> set:
    """Ansible's own list of task-level keywords, not a hand-maintained copy."""
    try:
        from ansible.playbook.task import Task

        attrs = getattr(Task, "fattributes", None) or getattr(Task, "_valid_attrs", None)
        if attrs:
            return set(attrs)
    except Exception:
        pass
    return {
        "name",
        "action",
        "args",
        "become",
        "become_user",
        "when",
        "loop",
        "register",
        "tags",
        "notify",
        "changed_when",
        "failed_when",
        "ignore_errors",
        "delegate_to",
        "vars",
        "until",
        "retries",
        "delay",
        "no_log",
        "check_mode",
        "environment",
        "run_once",
        "block",
    }


def _is_absent(value: Any) -> bool:
    """True when a prose field is reporting 'nothing here'."""
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    return bool(_ABSENT_RE.match(str(value)))


def _first_task(task_yaml: str) -> Optional[dict[str, Any]]:
    try:
        parsed = yaml.safe_load(task_yaml)
    except Exception:
        return None
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None
    return parsed if isinstance(parsed, dict) else None


def extract_gold(task_yaml: str) -> dict[str, Any]:
    """Recover verifiable facts from a task's YAML.

    Returns a dict of gold values, plus ``_extraction`` describing how the
    module was resolved: ``parser`` (Ansible's, authoritative) or ``fallback``
    (keyword subtraction, used when the module belongs to a collection that is
    not installed).
    """
    _ensure_loader()
    ds = _first_task(task_yaml)
    if ds is None:
        return {"_extraction": "unparseable"}

    action, args, delegate_to, how = _resolve_action(ds)

    task_level = {k: v for k, v in ds.items() if k in _task_keywords()}
    guarded = bool(_GUARD_ARGS & set(args))
    base = action.split(".")[-1] if action else ""

    if task_level.get("changed_when") is not None:
        idempotency = "explicit"
    elif base in _UNGUARDED:
        idempotency = "explicit" if guarded else "not_handled"
    else:
        idempotency = "implicit"

    loop_present = any(k == "loop" or k.startswith("with_") for k in ds)

    return {
        "module": action or "",
        "is_fqcn": bool(action and action.count(".") >= 2),
        "parameters": sorted(k for k in args if k != "_raw_params"),
        "idempotency": idempotency,
        "conditions": task_level.get("when") is not None,
        "loop": loop_present,
        "delegation": delegate_to is not None,
        "privilege_escalation": bool(task_level.get("become")),
        "change_detection": task_level.get("register") is not None
        or task_level.get("changed_when") is not None,
        "error_handling": any(
            task_level.get(k) is not None
            for k in ("ignore_errors", "failed_when", "rescue", "until")
        ),
        "_extraction": how,
    }


def _resolve_action(ds: dict[str, Any]) -> tuple[str, dict[str, Any], Any, str]:
    """Resolve (action, args, delegate_to) preferring Ansible's own parser."""
    try:
        from ansible.parsing.mod_args import ModuleArgsParser
        from ansible.utils.sentinel import Sentinel

        action, args, delegate_to = ModuleArgsParser(ds).parse()
        if delegate_to is Sentinel or delegate_to is None:
            delegate_to = None
        return action, dict(args or {}), delegate_to, "parser"
    except Exception:
        pass

    # Fallback: the module is the one key that is not a task keyword. Used when
    # the task targets a collection that is not installed locally.
    keywords = _task_keywords()
    candidates = [k for k in ds if k not in keywords]
    action = candidates[0] if candidates else ""
    raw = ds.get(action)
    if isinstance(raw, dict):
        args = dict(raw)
    elif isinstance(raw, str):
        args = dict(re.findall(r"(\w+)=(\S+)", raw))
    else:
        args = {}
    args.update(ds.get("args") or {})
    return action, args, ds.get("delegate_to"), "fallback"


# -- scoring ---------------------------------------------------------------


def score_task(gold: dict[str, Any], pred: Any) -> dict[str, Any]:
    """Score a prediction against deterministic gold.

    Returns ``{"score": float, "fields": {name: {...}}, "misses": [str]}``.
    Per-field partial credit rather than all-or-nothing, so an optimiser gets
    gradient instead of a cliff.
    """
    get = pred.get if isinstance(pred, dict) else lambda k, d=None: getattr(pred, k, d)
    fields: dict[str, dict[str, Any]] = {}
    misses: list[str] = []

    # module: compare on the final segment too, so a correct-but-unqualified
    # answer is partially credited rather than scored zero.
    g_mod, p_mod = str(gold.get("module", "")), str(get("module", "") or "")
    if g_mod and p_mod == g_mod:
        s = 1.0
    elif g_mod and p_mod.split(".")[-1] == g_mod.split(".")[-1]:
        s = 0.6
    else:
        s = 0.0
    fields["module"] = {"score": s, "gold": g_mod, "pred": p_mod}

    # is_fqcn
    p_fqcn = get("is_fqcn", None)
    fields["is_fqcn"] = {
        "score": 1.0 if bool(p_fqcn) == bool(gold.get("is_fqcn")) else 0.0,
        "gold": gold.get("is_fqcn"),
        "pred": p_fqcn,
    }

    # parameters: F1 over names. Precision matters -- invented parameters are
    # the failure mode worth punishing.
    g_params = set(gold.get("parameters") or [])
    p_raw = get("parameters", None) or []
    p_params = set()
    for item in p_raw:
        if isinstance(item, dict):
            p_params.add(str(item.get("name", "")).strip())
        elif hasattr(item, "name"):
            p_params.add(str(item.name).strip())
    p_params.discard("")
    if not g_params and not p_params:
        f1 = 1.0
    elif not g_params or not p_params:
        f1 = 0.0
    else:
        tp = len(g_params & p_params)
        prec = tp / len(p_params)
        rec = tp / len(g_params)
        f1 = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
    fields["parameters"] = {
        "score": f1,
        "gold": sorted(g_params),
        "pred": sorted(p_params),
        "invented": sorted(p_params - g_params),
        "missed": sorted(g_params - p_params),
    }

    # idempotency: categorical
    p_idem = str(get("idempotency", "") or "").strip().lower()
    fields["idempotency"] = {
        "score": 1.0 if p_idem == gold.get("idempotency") else 0.0,
        "gold": gold.get("idempotency"),
        "pred": p_idem,
    }

    # presence fields: did the model report something where something exists?
    for name in _PRESENCE_FIELDS:
        expected = bool(gold.get(name))
        reported = not _is_absent(get(name, None))
        fields[name] = {
            "score": 1.0 if reported == expected else 0.0,
            "gold": expected,
            "pred": reported,
        }

    total = sum(WEIGHTS[k] * v["score"] for k, v in fields.items() if k in WEIGHTS)
    for name, info in fields.items():
        if info["score"] < 1.0:
            misses.append(name)
    return {"score": round(total, 4), "fields": fields, "misses": misses}


def _gold_from(example: Any) -> dict[str, Any]:
    """Prefer gold already attached to the example; else derive it from YAML."""
    get = example.get if isinstance(example, dict) else lambda k, d=None: getattr(example, k, d)
    if get("module", None) is not None and get("parameters", None) is not None:
        return {
            k: get(k, None)
            for k in (
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
        }
    return extract_gold(get("task_yaml", "") or "")


def task_metric(example: Any, pred: Any, trace: Optional[Any] = None) -> float:
    """DSPy metric: structural groundedness of a task analysis, in [0, 1].

    Usable directly with ``BootstrapFewShot(metric=task_metric)`` or
    ``MIPROv2(metric=task_metric)``. When ``trace`` is not None DSPy is
    bootstrapping demonstrations and wants a strict bool, so a high bar is
    applied there.
    """
    result = score_task(_gold_from(example), pred)
    if trace is not None:
        return result["score"] >= 0.9
    return result["score"]


def task_feedback_metric(
    gold: Any,
    pred: Any,
    trace: Optional[Any] = None,
    pred_name: Optional[str] = None,
    pred_trace: Optional[Any] = None,
    program_trace: Optional[Any] = None,
) -> dict[str, Any]:
    """GEPA metric: score plus textual feedback naming the exact fields missed.

    GEPA rewrites instructions from this feedback, so it states what was wrong
    and what the source YAML actually says rather than only returning a number.
    """
    result = score_task(_gold_from(gold), pred)
    if not result["misses"]:
        return {"score": result["score"], "feedback": "All structural facts correct."}

    notes = []
    for name in result["misses"]:
        info = result["fields"][name]
        if name == "parameters":
            if info["invented"]:
                notes.append(
                    "parameters: invented {} -- these do not appear in the "
                    "task".format(info["invented"])
                )
            if info["missed"]:
                notes.append("parameters: omitted {}".format(info["missed"]))
        else:
            notes.append(
                "{}: reported {!r} but the task shows {!r}".format(name, info["pred"], info["gold"])
            )
    return {
        "score": result["score"],
        "feedback": "Report only what the task YAML states. " + " ".join(notes),
    }


# -- optional LLM judge for the prose fields -------------------------------


def judge_metric(example: Any, pred: Any, trace: Optional[Any] = None) -> float:
    """Score the prose fields with an LLM judge. Costs one LM call per example.

    Kept separate from :func:`task_metric` on purpose. The structural score is
    free, deterministic and reproducible; this one is none of those. Blending
    them into a single number would hide which half moved.
    """
    import dspy
    from llm_signatures import build_judge

    get = example.get if isinstance(example, dict) else lambda k, d=None: getattr(example, k, d)
    pget = pred.get if isinstance(pred, dict) else lambda k, d=None: getattr(pred, k, d)
    judge = dspy.Predict(build_judge())
    try:
        verdict = judge(
            task_yaml=get("task_yaml", "") or "",
            goal=str(pget("goal", "") or ""),
            role_in_play=str(pget("role_in_play", "") or ""),
            idempotency_mechanism=str(pget("idempotency_mechanism", "") or ""),
        )
        return float(verdict.score)
    except Exception:
        return 0.0


def composite_metric(
    example: Any,
    pred: Any,
    trace: Optional[Any] = None,
    structural_weight: float = 0.7,
) -> float:
    """Structural score plus judged prose. Use only once structural plateaus.

    Running this from the start wastes money: a model that cannot name the
    module correctly will not have written good prose either, and the free
    metric already catches that.
    """
    s = task_metric(example, pred)
    j = judge_metric(example, pred)
    return structural_weight * s + (1.0 - structural_weight) * j
