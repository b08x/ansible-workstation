# callback_plugins/rich_ci_formatter.py
"""
High-Contrast Ansible stdout Callback Plugin

Architecturally optimized for Continuous Integration (CI) environments, providing 
specialized, high-density telemetry rendering for dnf5, podman_image, and systemd modules.
Strictly prohibits the emission of unstructured JSON and default Ansible tracebacks.
"""

import time
from typing import Any, Dict, List

# Core Ansible Plugin Architecture Imports
from ansible.plugins.callback import CallbackBase
from ansible.executor.task_result import TaskResult
from ansible.playbook.task import Task

# Rich Library Imports for Terminal-Native Structural Serialization
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text

class CallbackModule(CallbackBase):
    """
    Custom Ansible callback plugin overriding default stdout to render 
    execution states as structured, high-contrast console output using the `rich` library.
    """
    # Strict integration parameters for the Ansible v2 Event API
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'rich_ci'

    def __init__(self) -> None:
        """
        Initialize the callback plugin, allocating memory for the global 
        rendering console and performance tracking dictionaries.
        """
        super().__init__()
        
        # Initialize a singular, global rich console for efficient stdout buffering.
        # force_terminal ensures ANSI rendering even within detached CI runners.
        self.console = Console(force_terminal=True, color_system="standard")
        
        # High-performance tracking dictionary for task execution durations, 
        # mapping the unique task UUID to a monotonic hardware timestamp.
        self.task_start_times: Dict[str, float] = {}

    def v2_playbook_on_task_start(self, task: Task, is_conditional: bool) -> None:
        """
        Intercept the initialization of a task to record a highly precise monotonic timestamp.
        """
        self.task_start_times[task._uuid] = time.monotonic()

    def _calculate_duration(self, task_uuid: str) -> str:
        """
        Calculate the elapsed execution time for a given task UUID via O(1) dictionary lookup.
        """
        start_time = self.task_start_times.get(task_uuid)
        if start_time:
            duration = time.monotonic() - start_time
            return f"{duration:.2f}s"
        return "0.00s"

    def v2_runner_on_ok(self, result: TaskResult) -> None:
        """
        Intercept successful task executions, dispatching the payload to 
        specialized IntentAST telemetry parsers based on the evaluated module action.
        """
        task_action: str = result._task.action
        task_name: str = result._task.get_name().strip()
        host_name: str = result._host.get_name()
        duration: str = self._calculate_duration(result._task._uuid)
        payload: Dict[str, Any] = result._result

        # STRICT SECURITY GATE: Enforce _ansible_no_log censorship immediately
        if payload.get('_ansible_no_log', False):
            self._render_generic_success(task_name, host_name, duration, "Output censored (no_log)")
            return

        # Route to specific structural parsers based on the target module context
        if task_action in ('ansible.builtin.dnf5', 'ansible.builtin.dnf'):
            self._render_dnf5_telemetry(task_name, host_name, duration, payload)
        elif task_action == 'containers.podman.podman_image':
            self._render_podman_telemetry(task_name, host_name, duration, payload)
        elif task_action == 'ansible.builtin.systemd':
            self._render_systemd_telemetry(task_name, host_name, duration, payload)
        else:
            # Fallback renderer for non-targeted module executions
            is_changed = payload.get('changed', False)
            status_text = "CHANGED" if is_changed else "OK"
            self._render_generic_success(task_name, host_name, duration, status_text, is_changed)

    def v2_runner_on_failed(self, result: TaskResult, ignore_errors: bool = False) -> None:
        """
        Intercept task failures, suppressing default Ansible tracebacks and 
        emitting isolated, high-contrast error panels.
        """
        task_name: str = result._task.get_name().strip()
        host_name: str = result._host.get_name()
        payload: Dict[str, Any] = result._result
        duration: str = self._calculate_duration(result._task._uuid)

        # STRICT SECURITY GATE: Prevent secret leakage during failures
        if payload.get('_ansible_no_log', False):
            self.console.print(Panel(
                Text("Task failed, but traceback and payload are censored due to no_log: true", style="bold red"),
                title=f"❌ FAILURE | {host_name} | {task_name}",
                border_style="red"
            ))
            return

        error_msg: str = payload.get('msg', 'An unknown execution error occurred.')
        exception: str = payload.get('exception', '')

        content = Text()
        content.append(f"Execution Duration: {duration}\n", style="cyan")
        content.append(f"Error Message: {error_msg}\n\n", style="bold red")

        # Safely render tracebacks without crashing the callback or emitting raw JSON
        if exception:
            content.append("Module Traceback:\n", style="bold yellow")
            content.append(exception, style="dim white")

        panel = Panel(
            content,
            title=f"❌ CRITICAL FAILURE | {host_name} | {task_name}",
            border_style="red",
            expand=False
        )
        self.console.print(panel)

    # -------------------------------------------------------------------------
    # Specialized IntentAST Structural Rendering Pipelines
    # -------------------------------------------------------------------------

    def _render_dnf5_telemetry(self, task: str, host: str, duration: str, payload: Dict[str, Any]) -> None:
        """
        Parses dnf5 transaction results, constructing a high-density mathematical table 
        of exact package state diffs.
        """
        table = Table(
            title=f"📦 DNF5 Transaction | {host} | {task} ({duration})", 
            show_header=True, 
            header_style="bold magenta"
        )
        table.add_column("Package Name", style="cyan")
        table.add_column("Action Taken", justify="center")
        table.add_column("Final State", justify="right")

        changes_found = False
        
        # Interrogate the diff payload structure
        diff_data = payload.get('diff', [])
        if isinstance(diff_data, list) and diff_data:
            for diff in diff_data:
                # Map diff before/after states to visual tabular rows
                if 'after' in diff and diff['after']:
                    table.add_row(diff.get('after_header', 'Unknown Package'), "Installed/Upgraded", "🟢 Present", style="green")
                    changes_found = True
                if 'before' in diff and diff['before']:
                    table.add_row(diff.get('before_header', 'Unknown Package'), "Removed/Erased", "🔴 Absent", style="red")
                    changes_found = True
        
        if not changes_found:
            table.add_row("All target packages", "Verified", "🔵 Synchronized", style="dim white")

        self.console.print(table)
        self.console.print("\n")

    def _render_podman_telemetry(self, task: str, host: str, duration: str, payload: Dict[str, Any]) -> None:
        """
        Parses podman_image module output, rendering OCI image build layers as hierarchical trees.
        """
        is_changed = payload.get('changed', False)
        status_color = "yellow" if is_changed else "green"
        
        root_tree = Tree(f"🐳 [bold {status_color}]Podman Image Engine | {host} | {task} ({duration})[/]")
        
        # Structurally map build logs from the standard output array
        stdout_lines: List[str] = payload.get('stdout_lines', [])
        if stdout_lines:
            build_branch = root_tree.add("[bold cyan]Container Build Sequence[/]")
            for line in stdout_lines:
                # Suppress empty line bloat for high-density CI reading
                if line.strip():
                    build_branch.add(Text(line.strip(), style="dim white"))
        
        # Extract and format resulting cryptographic image metadata
        image_data = payload.get('image', {})
        if image_data:
            meta_branch = root_tree.add("[bold magenta]OCI Image Metadata[/]")
            image_id = image_data.get('Id', 'Unknown SHA Digest')
            repo_tags = image_data.get('RepoTags', ['Untagged'])
            meta_branch.add(f"Digest: [bold white]{image_id}[/]")
            meta_branch.add(f"Tags: [bold white]{', '.join(repo_tags)}[/]")

        self.console.print(root_tree)
        self.console.print("\n")

    def _render_systemd_telemetry(self, task: str, host: str, duration: str, payload: Dict[str, Any]) -> None:
        """
        Parses systemd service states, emitting a highly abstract, compact status dashboard.
        """
        status_data = payload.get('status', {})
        state = payload.get('state', status_data.get('ActiveState', 'unknown'))
        
        # Deterministically map systemd active states to Unicode iconography
        if state in ('started', 'active'):
            icon, color = "✔️ RUNNING", "bold green"
        elif state in ('stopped', 'inactive'):
            icon, color = "⏸️ INACTIVE", "bold yellow"
        elif state == 'failed':
            icon, color = "❌ FAILED", "bold red"
        else:
            icon, color = "❓ UNKNOWN", "dim white"

        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", justify="right")
        table.add_column("Value", style=color)

        table.add_row("Daemon Target:", payload.get('name', 'Unknown Unit'))
        table.add_row("Active State:", icon)
        
        # Verify Boot and SysV linking states
        if 'enabled' in payload:
            is_enabled = payload['enabled']
            enabled_text = "🔗 Enabled (Symlinked to Target)" if is_enabled else "🛑 Disabled"
            table.add_row("Boot State:", enabled_text)
            
        if 'masked' in payload:
            is_masked = payload['masked']
            if is_masked:
                table.add_row("Mask State:", "🚫 Masked (Linked to /dev/null)")

        panel = Panel(table, title=f"⚙️ Systemd Transition | {host} | {task} ({duration})", border_style="blue", expand=False)
        self.console.print(panel)

    def _render_generic_success(self, task: str, host: str, duration: str, status: str, changed: bool = False) -> None:
        """
        Fallback renderer enforcing clean, single-line telemetry for modules 
        without specialized TUI implementations.
        """
        color = "yellow" if changed else "green"
        self.console.print(f"[{color}][{status}][/] {host} | {task} (Execution: {duration})")