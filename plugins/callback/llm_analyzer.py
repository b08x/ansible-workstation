# -*- coding: utf-8 -*-
# Copyright (c) 2023 Sagi Shnaidman <sshnaidm@gmail.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from ansible.plugins.callback import CallbackBase

__metaclass__ = type

# Ansible's plugin loader imports this file directly rather than as part of a
# package, so the support modules are not importable without help.
#
# They deliberately live in ../callback_utils, NOT beside this file: the loader
# globs *.py in every callback_plugins path, imports each match and demands a
# CallbackModule attribute, so a helper placed here would be imported by Ansible
# and then rejected with a warning -- and would end up in sys.modules twice,
# under two names, with two copies of its state.
_UTILS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "callback_utils"
)
if not os.path.isdir(_UTILS_DIR):
    raise ImportError(
        f"llm_analyzer requires its support modules at {_UTILS_DIR}. Ansible reports a "
        "missing directory here only as 'Skipping plugin', so fail loudly "
        "instead."
    )
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

from llm_engine import AnsibleAnalyzer
from llm_pool import AnalysisPool
from llm_report import (
    render_play_markdown,
    render_style_section,
    render_task_markdown,
    save_markdown,
    save_suggestions,
)
from llm_style import analyze_style
from llm_suggestions import generate_structured_suggestions
from llm_trace_store import TraceStore

DOCUMENTATION = """
    name: llm_analyzer
    type: notification
    short_description: Analyzes Ansible tasks and playbooks with various AI models
    description:
      - Analyzes Ansible tasks and playbooks using different AI providers
      - Validates API keys before playbook execution
      - Runs analysis on a bounded background worker pool so the playbook is
        not stalled by an LLM round trip per task (see O(async_workers))
      - Saves analysis to markdown files in llm_analysis directory, and every
        prediction to an append-only trace store for later optimisation
      - Streams explanations to the console only when O(async_workers=0)
      - Automatically disables if API key validation fails
    requirements:
      - enable in configuration - see examples section below for details
      - install required provider libraries (openai, google.generativeai, etc.)

    options:
      provider:
        description: AI provider to use
        choices: ['openai', 'gemini', 'groq', 'openrouter', 'cohere', 'anthropic']
        default: openai
        env:
          - name: AI_PROVIDER
        ini:
          - section: callback_llm_analyzer
            key: provider
      api_key:
        description: |
          API key for the chosen provider. Can be provided directly or via environment variables:
          - For OpenAI: OPENAI_API_KEY
          - For Gemini: GEMINI_API_KEY or GOOGLE_API_KEY
          - For Groq: GROQ_API_KEY
          - For OpenRouter: OPENROUTER_API_KEY
          - For Cohere: COHERE_API_KEY
          - For Anthropic: ANTHROPIC_API_KEY
          The API key must be set either through this option or the corresponding environment variable.
        env:
          - name: OPENAI_API_KEY
          - name: GEMINI_API_KEY
          - name: GROQ_API_KEY
          - name: OPENROUTER_API_KEY
          - name: COHERE_API_KEY
          - name: ANTHROPIC_API_KEY
        ini:
          - section: callback_llm_analyzer
            key: api_key
      model:
        description: Model to use for the chosen provider
        default: gpt-4
        env:
          - name: AI_MODEL
        ini:
          - section: callback_llm_analyzer
            key: model
      temperature:
        description: Temperature for AI response
        default: 0.4
        env:
          - name: AI_TEMPERATURE
        ini:
          - section: callback_llm_analyzer
            key: temperature
      max_tokens:
        description:
          - Maximum tokens the model may generate per analysis response.
          - >
            This is an output budget, not a context window. Setting it to the
            model's full context length does not buy longer analyses; it only
            raises the ceiling DSPy quotes back in its truncation warning,
            which reports this configured value rather than the limit an
            individual request actually used.
        type: int
        default: 1000
        env:
          - name: AI_MAX_TOKENS
        ini:
          - section: callback_llm_analyzer
            key: max_tokens
      async_workers:
        description:
          - Number of background threads that perform LLM analysis.
          - >
            Ansible calls C(v2_playbook_on_task_start) on the main thread and
            waits for it to return before dispatching the task, so a synchronous
            analysis adds one full LLM round trip to every task in the playbook.
            With workers the handler only serialises the task and enqueues it.
          - Set to V(0) for the legacy synchronous behaviour, which also streams
            each explanation to the console in playbook order.
        type: int
        default: 4
        env:
          - name: AI_ASYNC_WORKERS
        ini:
          - section: callback_llm_analyzer
            key: async_workers
      queue_maxsize:
        description:
          - Maximum number of pending analyses held in memory.
          - >
            A bound is required: an unbounded queue turns a fast playbook into
            unbounded memory growth and unbounded spend, because tasks are
            enqueued far faster than an LLM can answer them.
        type: int
        default: 64
        env:
          - name: AI_QUEUE_MAXSIZE
        ini:
          - section: callback_llm_analyzer
            key: queue_maxsize
      queue_full_policy:
        description:
          - What to do when the queue is full.
          - V(block) throttles the playbook to the analysis rate, losing nothing.
          - V(drop) never delays the playbook and records a dropped-trace count.
        choices: ['block', 'drop']
        default: block
        env:
          - name: AI_QUEUE_FULL_POLICY
        ini:
          - section: callback_llm_analyzer
            key: queue_full_policy
      drain_timeout:
        description:
          - Seconds to wait at the end of a playbook for pending analyses.
          - Anything still queued when this expires is abandoned and counted.
        type: float
        default: 120.0
        env:
          - name: AI_DRAIN_TIMEOUT
        ini:
          - section: callback_llm_analyzer
            key: drain_timeout

    examples: |
      # Enable the callback plugin in ansible.cfg
      [defaults]
      callbacks_enabled = llm_analyzer

      # Configure the plugin in ansible.cfg
      [callback_llm_analyzer]
      provider = openai
      api_key = sk-xxx  # Or set via OPENAI_API_KEY environment variable
      model = gpt-4
      temperature = 0.4
      max_tokens = 1000

      # Example using environment variables with Gemini
      export AI_PROVIDER=gemini
      export GEMINI_API_KEY=your-key
      export AI_MODEL=gemini-1.5-pro
      ansible-playbook playbook.yml

      # Example using Groq
      [callback_llm_analyzer]
      provider = groq
      api_key = gsk-xxx  # Or set via GROQ_API_KEY environment variable
      model = llama-3.3-70b-versatile

      # Example using Cohere
      [callback_llm_analyzer]
      provider = cohere
      api_key = xxx  # Or set via COHERE_API_KEY environment variable
      model = command-r-plus-08-2024

      # Example using OpenRouter
      [callback_llm_analyzer]
      provider = openrouter
      api_key = sk-xxx  # Or set via OPENROUTER_API_KEY environment variable
      model = anthropic/claude-3-opus
"""


class CallbackModule(CallbackBase):
    """Analyse each play and task with an LLM, off Ansible's main thread.

    The division of labour is the whole design. ``v2_playbook_on_*`` runs on
    Ansible's thread and does only what needs the live object -- serialise it,
    because Ansible mutates and reuses Task objects as the play advances. Every
    other step (style checking, the LLM round trip, trace + markdown writing)
    is a pure function of that captured text and happens on the pool.
    """

    CALLBACK_VERSION = 1.1
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "llm_analyzer"
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super().__init__()
        self.analyzer = None
        self.disabled = False
        self.analysis_dir = Path("llm_analysis")
        self.analysis_dir.mkdir(exist_ok=True)
        self.store = TraceStore(self.analysis_dir / "traces")
        self.task_count = 0
        self.play_count = 0
        # Replaced in set_options once the options are readable. A zero-worker
        # pool runs inline, which is also the right behaviour if the plugin is
        # disabled before it ever gets configured.
        self.pool = AnalysisPool(self._process)

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super().set_options(task_keys=task_keys, var_options=var_options, direct=direct)

        provider = self.get_option("provider")
        # Provider-specific environment variable wins over the generic
        # api_key in ansible.cfg.
        api_key = os.getenv(f"{provider.upper()}_API_KEY") or self.get_option("api_key")

        try:
            self.analyzer = AnsibleAnalyzer(
                provider=provider,
                api_key=api_key,
                model=self.get_option("model"),
                temperature=float(self.get_option("temperature")),
                max_tokens=self.get_option("max_tokens"),
            )
            self.analyzer.setup()
            reason = self.analyzer.validate()
            if reason:
                self.disabled = True
                print(
                    f"\nLLM Analyzer disabled: {reason}.\n"
                    "LLM analysis will be skipped; the playbook continues."
                )
                return
        except Exception as e:
            self.disabled = True
            print(
                f"\nLLM Analyzer disabled: Failed to initialize provider "
                f"'{provider}': {e!s}. LLM analysis will be skipped."
            )
            return

        workers, maxsize = 4, 64
        full_policy, drain_timeout = "block", 120.0
        try:
            workers = max(0, int(self.get_option("async_workers")))
            maxsize = max(1, int(self.get_option("queue_maxsize")))
            full_policy = self.get_option("queue_full_policy")
            drain_timeout = float(self.get_option("drain_timeout"))
        except (TypeError, ValueError):
            workers, maxsize = 4, 64

        self.store.start_run(
            provider=provider,
            model=self.analyzer.model_string,
            temperature=self.analyzer.temperature,
            max_tokens=self.analyzer.max_tokens,
            signature_version=self.analyzer.signature_version,
            async_workers=workers,
        )
        self.pool = AnalysisPool(
            self._process,
            workers=workers,
            maxsize=maxsize,
            full_policy=full_policy,
            drain_timeout=drain_timeout,
        )

    # -- Ansible's thread: capture and hand off ---------------------------

    def v2_playbook_on_task_start(self, task, is_conditional):
        """Serialise the task and hand it off. Runs on Ansible's main thread."""
        if self.disabled or self.analyzer is None:
            return

        self.task_count += 1
        self.pool.submit(
            {
                "kind": "task",
                "count": self.task_count,
                "name": task.get_name(),
                "subject_uuid": str(getattr(task, "_uuid", "") or ""),
                "source_yaml": self._task_to_yaml(task),
            }
        )

    def v2_playbook_on_play_start(self, play):
        if self.disabled or self.analyzer is None:
            return

        self.play_count += 1
        self.pool.submit(
            {
                "kind": "play",
                "count": self.play_count,
                "name": play.get_name(),
                "subject_uuid": str(getattr(play, "_uuid", "") or ""),
                "source_yaml": self._play_to_yaml(play),
            }
        )

    def v2_playbook_on_stats(self, stats):
        """Drain pending analyses, then close the run record.

        Draining before end_run is what makes the run record trustworthy: it is
        written once, after every analysis it counts has actually landed.
        """
        self.pool.drain()
        if self.pool.dropped or self.pool.abandoned:
            self.pool.say(
                f"LLM Analyzer: {self.pool.dropped} analyses dropped (queue full), "
                f"{self.pool.abandoned} abandoned at drain timeout."
            )
        if self.store.run_id:
            self.store.end_run(
                task_analyses=self.task_count,
                play_analyses=self.play_count,
                dropped=self.pool.dropped,
                abandoned=self.pool.abandoned,
            )

    # -- worker thread: analyse and record --------------------------------

    def _process(self, job: dict[str, Any], stream: bool) -> None:
        """Analyse one captured subject. Runs on a worker unless async is off."""
        kind = job["kind"]
        source_yaml = job["source_yaml"]

        style_violations = analyze_style(source_yaml)
        if kind == "task":
            outputs, meta = self.analyzer.analyze_task(source_yaml, style_violations)
        else:
            outputs, meta = self.analyzer.analyze_play(source_yaml, style_violations)

        analysis_id = self.store.record_analysis(
            kind=kind,
            name=job["name"],
            subject_uuid=job["subject_uuid"],
            source_yaml=source_yaml,
            style_violations=style_violations,
            outputs=outputs,
            **meta,
        )

        if meta.get("error"):
            self.pool.say("LLM Analyzer [{}]: {}".format(job["name"], meta["error"]))
            return

        if kind == "task":
            explanation = render_task_markdown(outputs)
        else:
            explanation = render_play_markdown(outputs)

        # Only the synchronous path streams to the console. Worker output would
        # arrive detached from the task it describes and interleave with
        # Ansible's own, so async runs leave the record to disk.
        if stream:
            print(f"Explanation: \n{explanation}")
            if style_violations:
                print("\n⚠️  Style Guide Violations Found:")
                for violation in style_violations:
                    print(f"  • Line {violation['line']}: {violation['message']}")

        save_markdown(
            self.analysis_dir,
            explanation + render_style_section(style_violations),
            kind,
            job["name"],
            analysis_id=analysis_id,
            count=job["count"],
        )

    # -- serialisation ----------------------------------------------------

    def _task_to_yaml(self, task) -> str:
        """Serialise a task, falling back to public attributes if get_ds() fails."""
        try:
            return yaml.dump([json.loads(json.dumps(task.get_ds()))])
        except (AttributeError, TypeError) as e:
            print(f"Warning: Could not access task data structure: {e}")
            task_dict = {
                "name": str(getattr(task, "name", "Unknown Task")),
                "action": str(getattr(task, "action", "Unknown Action")),
            }
            try:
                if getattr(task, "args", None):
                    args_data = dict(task.args) if hasattr(task.args, "items") else task.args
                    json.dumps(args_data)
                    task_dict.update(args_data)
            except (TypeError, ValueError, AttributeError):
                task_dict["args"] = "Unable to serialize task arguments"
            return yaml.dump([task_dict])

    def _play_to_yaml(self, play) -> str:
        """Serialise a play, falling back to public attributes if get_ds() fails."""
        try:
            return yaml.dump(json.loads(json.dumps(play.get_ds())))
        except (AttributeError, TypeError) as e:
            print(f"Warning: Could not access play data structure: {e}")
            hosts = getattr(play, "hosts", [])
            return yaml.dump(
                {
                    "name": str(getattr(play, "name", "Unknown Play")),
                    "hosts": list(hosts) if hasattr(hosts, "__iter__") else ["Unknown"],
                    "gather_facts": bool(getattr(play, "gather_facts", True)),
                }
            )

    # -- style pass, exposed for out-of-band callers -----------------------

    def analyze_style(self, yaml_content: str) -> list[dict[str, Any]]:
        """Analyze YAML content for Ansible style guide violations."""
        return analyze_style(yaml_content)

    def generate_structured_suggestions(
        self, yaml_content: str, file_path: str = "ansible_file.yml"
    ) -> str:
        """Generate structured suggestions for LLM processing in DSPy format."""
        return generate_structured_suggestions(yaml_content, file_path)

    def _save_structured_suggestions(
        self, suggestions: str, analysis_type: str, name: Optional[str] = None
    ):
        """Save structured suggestions for LLM processing."""
        count = self.task_count if analysis_type == "task" else self.play_count
        return save_suggestions(self.analysis_dir, suggestions, analysis_type, name, count=count)
