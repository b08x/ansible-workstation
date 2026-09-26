# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""DSPy-backed LLM engine for llm_analyzer.

Holds everything that talks to a model: provider/key resolution, the two
``dspy.Predict`` programs built from :mod:`llm_signatures`, the startup
reachability check, and the per-call metadata the trace store records.

Nothing in here knows about Ansible. It takes YAML text and returns
``(outputs, meta)``, which is what makes it directly exercisable from
``scripts/llm_trainset.py`` without standing up a playbook.
"""

from __future__ import absolute_import, division, print_function

import os
import time
from typing import Any, Optional

__metaclass__ = type

# Provider routing is delegated to litellm via dspy.LM, which is why the six
# hand-written client branches that used to live here are gone. litellm's model
# strings are "<provider>/<model>"; openrouter models are themselves namespaced
# ("openrouter/anthropic/claude-3-opus"), so a model that already carries the
# provider prefix is passed through untouched.
PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "cohere": "COHERE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Startup reachability probe. The budget is deliberately not minimal: a
# reasoning model emits its preamble before any answer, so a five-token cap
# returns finish_reason="length" with a null message on a perfectly healthy
# provider. Observed cost of a passing probe is well under this ceiling; the
# headroom exists so the check measures the provider, not the model's verbosity.
_PROBE_PROMPT = "Reply with the single word: ok"
_PROBE_MAX_TOKENS = 256


class AnsibleAnalyzer:
    """DSPy-backed analyzer for Ansible tasks and plays.

    ``dspy`` is imported in :meth:`setup`, never at module scope. Ansible loads
    every enabled callback plugin in-process at ``ansible-playbook`` startup, so
    a module-level ``import dspy`` (which pulls litellm, pydantic and optuna)
    would tax every playbook run, including ones where analysis never fires.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.lm = None
        self.signature_version = None
        self._dspy = None
        self._task_program = None
        self._play_program = None

    @property
    def model_string(self) -> str:
        """litellm model identifier for the configured provider/model pair."""
        if "/" in self.model and self.model.split("/", 1)[0] == self.provider:
            return self.model
        return f"{self.provider}/{self.model}"

    def setup(self) -> None:
        if not self.api_key:
            raise ValueError(f"API key not provided for {self.provider}")

        import dspy  # deferred: see class docstring
        from llm_signatures import SIGNATURE_VERSION, build

        env_var = PROVIDER_ENV_VARS.get(self.provider)
        if env_var:
            os.environ[env_var] = self.api_key

        lm_kwargs = {"model": self.model_string, "api_key": self.api_key}
        if self.temperature is not None:
            lm_kwargs["temperature"] = self.temperature
        if self.max_tokens:
            lm_kwargs["max_tokens"] = self.max_tokens

        self.lm = dspy.LM(**lm_kwargs)
        # configure() records the calling thread as owner and raises if another
        # thread ever calls it. This runs from set_options on the main thread;
        # workers bind the LM with dspy.context instead, which is thread-safe.
        dspy.configure(lm=self.lm, track_usage=True)
        self._dspy = dspy

        task_sig, play_sig = build()
        self.signature_version = SIGNATURE_VERSION
        self._task_program = dspy.Predict(task_sig)
        self._play_program = dspy.Predict(play_sig)

    def validate(self) -> Optional[str]:
        """Confirm the model answers. Returns None on success, else the reason.

        The reason is classified rather than assumed. Reporting every startup
        failure as a bad API key sends the reader after the one thing that is
        often fine: a wrong model slug, an unreachable endpoint and a rate
        limit all arrive here as exceptions too.
        """
        if not self.api_key:
            return f"no API key provided for {self.provider}"
        # No retries for the startup check: the common failures here (unknown
        # model, bad key) are not retryable, and litellm's default retries turn
        # one config mistake into several seconds of playbook startup.
        #
        # This is set on the LM, not passed per call. dspy.LM.forward folds
        # per-call kwargs into the request dict and *also* passes its own
        # num_retries alongside it, so litellm.completion() receives the
        # argument twice and raises TypeError before any request is made.
        previous_retries = getattr(self.lm, "num_retries", None)
        self.lm.num_retries = 0
        try:
            outputs = self.lm(_PROBE_PROMPT, max_tokens=_PROBE_MAX_TOKENS)
        except Exception as e:
            return f"{self._classify(e)} for {self.provider} [{self.model_string}]: {e}"
        finally:
            if previous_retries is not None:
                self.lm.num_retries = previous_retries

        # An exception is not the only way this check fails. A reasoning model
        # that spends the whole budget on its preamble returns HTTP 200 with
        # finish_reason="length" and a null message, which would otherwise be
        # read as a healthy provider right up until the first real analysis
        # returns nothing.
        if not self._probe_text(outputs):
            return (
                f"empty response from {self.provider} [{self.model_string}]: the "
                f"model returned no content within {_PROBE_MAX_TOKENS} tokens"
            )
        return None

    @staticmethod
    def _probe_text(outputs) -> str:
        """Text of a legacy-path LM call, which yields str or dict entries.

        A dict entry carries the completion under "text" and, for reasoning
        models, the discarded preamble under "reasoning_content". Only "text"
        counts as an answer.
        """
        if not outputs:
            return ""
        first = outputs[0]
        if isinstance(first, dict):
            first = first.get("text")
        return (first or "").strip()

    @staticmethod
    def _classify(exc: Exception) -> str:
        """Name the failure so the message points at the thing to change."""
        name = type(exc).__name__
        text = str(exc).lower()
        if "notfound" in name.lower() or "404" in text or ("model" in text and "exist" in text):
            return "model not found (check the model slug)"
        if "authentication" in name.lower() or "401" in text or "api key" in text:
            return "authentication rejected (check the API key)"
        if "ratelimit" in name.lower() or "429" in text:
            return "rate limited"
        if "timeout" in name.lower() or "connection" in name.lower():
            return "could not reach the provider"
        if "got multiple values for" in text or "unexpected keyword argument" in text:
            return (
                "callback/dspy call-signature mismatch (a bug here, not your "
                "configuration -- an LM argument collided inside dspy)"
            )
        return f"startup check failed ({name})"

    # -- analysis ---------------------------------------------------------

    @staticmethod
    def _format_violations(style_violations: Optional[list[dict[str, Any]]]) -> str:
        if not style_violations:
            return ""
        lines = []
        for v in style_violations:
            entry = "- Line {} ({}): {}".format(v.get("line"), v.get("type"), v.get("message"))
            ref = v.get("reference", "")
            if ref:
                entry += f" [{ref}]"
            lines.append(entry)
        return "\n".join(lines)

    def _run(self, program, **kwargs):
        """Execute a program, returning (outputs, metadata). Never raises."""
        start = time.monotonic()
        meta = {
            "model": self.model_string,
            "provider": self.provider,
            "signature_version": self.signature_version,
            "latency_ms": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error": None,
        }
        try:
            # Thread-local override: a worker thread does not reliably inherit
            # the owner thread's configured LM, and must not call configure().
            with self._dspy.context(lm=self.lm):
                prediction = program(**kwargs)
        except Exception as e:
            meta["latency_ms"] = (time.monotonic() - start) * 1000.0
            meta["error"] = f"{type(e).__name__}: {e!s}"
            return {}, meta

        meta["latency_ms"] = (time.monotonic() - start) * 1000.0
        try:
            usage = prediction.get_lm_usage() or {}
            for entry in usage.values():
                meta["prompt_tokens"] = entry.get("prompt_tokens")
                meta["completion_tokens"] = entry.get("completion_tokens")
                break
        except Exception:
            pass

        outputs = {}
        for key, value in prediction.items():
            if key == "reasoning":
                continue
            outputs[key] = _jsonable(value)
        return outputs, meta

    def analyze_task(self, task_yaml, style_violations=None):
        if self._task_program is None:
            return {}, {"error": "analyzer not initialised"}
        return self._run(
            self._task_program,
            task_yaml=task_yaml,
            style_observations=self._format_violations(style_violations),
        )

    def analyze_play(self, play_yaml, style_violations=None):
        if self._play_program is None:
            return {}, {"error": "analyzer not initialised"}
        return self._run(
            self._play_program,
            play_yaml=play_yaml,
            style_observations=self._format_violations(style_violations),
        )


def _jsonable(value: Any) -> Any:
    """Coerce pydantic models and enums out of a prediction into plain data."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value
