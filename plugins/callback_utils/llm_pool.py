# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
"""Bounded background worker pool for llm_analyzer.

Ansible calls ``v2_playbook_on_task_start`` on the main thread and waits for it
to return before dispatching the task, so a synchronous analysis adds one full
LLM round trip to *every* task in the playbook. This pool exists so the handler
only serialises the task and enqueues it.

Two design constraints are load-bearing:

* The queue is bounded. An unbounded queue turns a fast playbook into unbounded
  memory growth and unbounded spend, because tasks are enqueued far faster than
  a model can answer them.
* The workers are daemons. If the playbook is killed, pending analyses are worth
  nothing and must not keep the process alive. The orderly path calls
  :meth:`drain` explicitly at end of run.

``workers=0`` selects the legacy synchronous behaviour: :meth:`submit` runs the
handler inline with ``stream=True`` so explanations reach the console in
playbook order.
"""

from __future__ import absolute_import, division, print_function

import contextlib
import queue
import threading
import time
from typing import Any, Callable

__metaclass__ = type


class AnalysisPool:
    """Runs ``handler(job, stream)`` on background threads, or inline."""

    def __init__(
        self,
        handler: Callable[[dict[str, Any], bool], None],
        workers: int = 0,
        maxsize: int = 64,
        full_policy: str = "block",
        drain_timeout: float = 120.0,
    ):
        self._handler = handler
        self.full_policy = full_policy
        self.drain_timeout = drain_timeout
        self.dropped = 0
        self.abandoned = 0
        self._print_lock = threading.Lock()
        self._queue = None
        self._workers = []
        if workers:
            self._queue = queue.Queue(maxsize=max(1, maxsize))
            for i in range(workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"llm_analyzer-{i}",
                    daemon=True,
                )
                t.start()
                self._workers.append(t)

    def submit(self, job: dict[str, Any]) -> None:
        """Hand a job to the pool, or run it inline when async is disabled."""
        if self._queue is None:
            self._handler(job, True)
            return
        if self.full_policy == "drop":
            try:
                self._queue.put_nowait(job)
            except queue.Full:
                self.dropped += 1
            return
        self._queue.put(job)

    def say(self, message: str) -> None:
        """Print without interleaving output from several workers."""
        with self._print_lock:
            print(message)

    def _worker_loop(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:  # shutdown sentinel
                self._queue.task_done()
                return
            try:
                self._handler(job, False)
            except Exception as e:  # a worker must outlive any single job
                self.say(f"LLM Analyzer worker error: {type(e).__name__}: {e}")
            finally:
                self._queue.task_done()

    def drain(self) -> int:
        """Wait out pending analyses. Returns (and records) the number abandoned."""
        if self._queue is None:
            return 0
        deadline = time.monotonic() + self.drain_timeout
        joiner = threading.Thread(target=self._queue.join, daemon=True)
        joiner.start()
        joiner.join(self.drain_timeout)
        # Queue.join() has no timeout, so it is joined through a thread. If the
        # joiner is still alive the deadline expired and work remains.
        self.abandoned = self._queue.qsize() if joiner.is_alive() else 0

        for _ in self._workers:
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(None)
        # One shared deadline, not a per-worker timeout: N workers each granted
        # their own grace period would make the real ceiling drain_timeout + N
        # seconds. Workers are daemons, so any straggler dies with the process.
        for t in self._workers:
            t.join(timeout=max(0.0, min(1.0, deadline + 1.0 - time.monotonic())))
        return self.abandoned
