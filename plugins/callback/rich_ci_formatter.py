from __future__ import annotations

# callback_plugins/rich_ci_formatter.py
"""
High-Contrast Ansible stdout Callback Plugin

Architecturally optimized for Continuous Integration (CI) environments, providing
specialized, high-density telemetry rendering for dnf5, podman_image, systemd, and capability probe modules.
Strictly prohibits the emission of unstructured JSON and default Ansible tracebacks.
"""

import os
import re
import time
from typing import Any, Dict, List

from ansible.executor.task_result import TaskResult
from ansible.playbook.task import Task

# Core Ansible Plugin Architecture Imports
from ansible.plugins.callback import CallbackBase

# Rich Library Imports for Terminal-Native Structural Serialization
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

__all__ = ["CallbackModule"]


class CallbackModule(CallbackBase):
    """
    Custom Ansible callback plugin overriding default stdout to render
    execution states as structured, high-contrast console output using the `rich` library.
    """

    # Strict integration parameters for the Ansible v2 Event API
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "rich_ci"

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
        if payload.get("_ansible_no_log", False):
            self._render_generic_success(task_name, host_name, duration, "Output censored (no_log)")
            return

        # Route to specific structural parsers based on the target module context
        if task_action in ("ansible.builtin.dnf5", "ansible.builtin.dnf"):
            self._render_dnf5_telemetry(task_name, host_name, duration, payload)
        elif task_action == "containers.podman.podman_image":
            self._render_podman_telemetry(task_name, host_name, duration, payload)
        elif task_action == "ansible.builtin.systemd":
            self._render_systemd_telemetry(task_name, host_name, duration, payload)
        elif self._is_probe_task(task_name, result._task, payload):
            self._render_probe_telemetry(task_name, host_name, duration, payload)
        else:
            # Fallback renderer for non-targeted module executions
            is_changed = payload.get("changed", False)
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
        if payload.get("_ansible_no_log", False) or payload.get("censored"):
            self.console.print("")
            self.console.print(
                Panel(
                    Text(
                        "Task failed, but traceback and payload are censored due to no_log: true",
                        style="bold red",
                    ),
                    title=f"❌ FAILURE | {host_name} | {task_name}",
                    border_style="red",
                )
            )
            self.console.print("")
            return

        error_msg: str = payload.get("msg", "An unknown execution error occurred.")
        exception: str = payload.get("exception", "")

        content = Text()
        content.append(f"Execution Duration: {duration}\n", style="cyan")
        content.append(f"Error Message: {error_msg}\n", style="bold red")

        # Safely render tracebacks without crashing the callback or emitting raw JSON
        if exception:
            content.append("\nModule Traceback:\n", style="bold yellow")
            content.append(exception + "\n", style="dim white")

        # Extract and truncate standard streams
        def _get_stream_lines(primary: str, fallback: str) -> List[str]:
            lines = payload.get(f"{primary}_lines")
            if isinstance(lines, list):
                return lines
            text = payload.get(primary)
            if not text:
                text = payload.get(fallback, "")
            if text and isinstance(text, str):
                return text.splitlines()
            return []

        stdout_lines = _get_stream_lines("stdout", "module_stdout")
        if stdout_lines:
            content.append("\nStandard Output (Last 20 Lines):\n", style="bold blue")
            content.append("\n".join(stdout_lines[-20:]) + "\n", style="dim white")

        stderr_lines = _get_stream_lines("stderr", "module_stderr")
        if stderr_lines:
            content.append("\nStandard Error (Last 20 Lines):\n", style="bold magenta")
            content.append("\n".join(stderr_lines[-20:]) + "\n", style="dim white")

        panel = Panel(
            content,
            title=f"❌ CRITICAL FAILURE | {host_name} | {task_name}",
            border_style="red",
            expand=False,
        )
        self.console.print("")
        self.console.print(panel)
        self.console.print("")

    def v2_runner_on_unreachable(self, result: TaskResult) -> None:
        """
        Intercept unreachable host events, suppressing default Ansible tracebacks and
        emitting isolated, high-contrast critical error panels.
        """
        task_name: str = result._task.get_name().strip()
        host_name: str = result._host.get_name()
        payload: Dict[str, Any] = result._result
        duration: str = self._calculate_duration(result._task._uuid)

        # STRICT SECURITY GATE: Prevent secret leakage during unreachable events
        if payload.get("_ansible_no_log", False) or payload.get("censored"):
            self.console.print("")
            self.console.print(
                Panel(
                    Text(
                        "Host is unreachable, but traceback and payload are censored due to no_log: true",
                        style="bold red",
                    ),
                    title=f"🚨 HOST UNREACHABLE | {host_name} | {task_name}",
                    border_style="red",
                )
            )
            self.console.print("")
            return

        error_msg: str = payload.get("msg", "Host is unreachable.")

        content = Text()
        content.append(f"Execution Duration: {duration}\n", style="cyan")
        content.append(f"Unreachable Details:\n{error_msg}\n", style="bold red")

        panel = Panel(
            content,
            title=f"🚨 HOST UNREACHABLE | {host_name} | {task_name}",
            border_style="red",
            expand=False,
        )
        self.console.print("")
        self.console.print(panel)
        self.console.print("")

    def v2_runner_on_skipped(self, result: TaskResult) -> None:
        """
        Intercept skipped task executions, rendering concise single-line telemetry
        when display of skipped hosts is enabled.
        """
        if getattr(self._display, "display_skipped_hosts", True):
            task_name: str = result._task.get_name().strip()
            host_name: str = result._host.get_name()
            duration: str = self._calculate_duration(result._task._uuid)
            self.console.print(
                f"[cyan][SKIPPED][/] {host_name} | {task_name} (Execution: {duration})"
            )

    # -------------------------------------------------------------------------
    # Specialized IntentAST Structural Rendering Pipelines
    # -------------------------------------------------------------------------

    def _render_dnf5_telemetry(
        self, task: str, host: str, duration: str, payload: Dict[str, Any]
    ) -> None:
        """
        Parses dnf5 transaction results, constructing a high-density mathematical table
        of exact package state diffs.
        """
        table = Table(
            title=f"📦 DNF5 Transaction | {host} | {task} ({duration})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Package Name", style="cyan")
        table.add_column("Action Taken", justify="center")
        table.add_column("Final State", justify="right")

        changes_found = False

        # Interrogate the diff payload structure
        diff_data = payload.get("diff", [])
        if isinstance(diff_data, list) and diff_data:
            for diff in diff_data:
                # Map diff before/after states to visual tabular rows
                if "after" in diff and diff["after"]:
                    table.add_row(
                        diff.get("after_header", "Unknown Package"),
                        "Installed/Upgraded",
                        "🟢 Present",
                        style="green",
                    )
                    changes_found = True
                if "before" in diff and diff["before"]:
                    table.add_row(
                        diff.get("before_header", "Unknown Package"),
                        "Removed/Erased",
                        "🔴 Absent",
                        style="red",
                    )
                    changes_found = True

        if not changes_found:
            table.add_row("All target packages", "Verified", "🔵 Synchronized", style="dim white")

        self.console.print("")
        self.console.print(table)
        self.console.print("")

    def _render_podman_telemetry(
        self, task: str, host: str, duration: str, payload: Dict[str, Any]
    ) -> None:
        """
        Parses podman_image module output, rendering OCI image build layers as hierarchical trees.
        """
        is_changed = payload.get("changed", False)
        status_color = "yellow" if is_changed else "green"

        root_tree = Tree(
            f"🐳 [bold {status_color}]Podman Image Engine | {host} | {task} ({duration})[/]"
        )

        # Structurally map build logs from the standard output array
        stdout_lines: List[str] = payload.get("stdout_lines", [])
        if stdout_lines:
            build_branch = root_tree.add("[bold cyan]Container Build Sequence[/]")
            for line in stdout_lines:
                # Suppress empty line bloat for high-density CI reading
                if line.strip():
                    build_branch.add(Text(line.strip(), style="dim white"))

        # Extract and format resulting cryptographic image metadata
        image_data = payload.get("image", {})
        if image_data:
            meta_branch = root_tree.add("[bold magenta]OCI Image Metadata[/]")
            image_id = image_data.get("Id", "Unknown SHA Digest")
            repo_tags = image_data.get("RepoTags", ["Untagged"])
            meta_branch.add(f"Digest: [bold white]{image_id}[/]")
            meta_branch.add(f"Tags: [bold white]{', '.join(repo_tags)}[/]")

        self.console.print("")
        self.console.print(root_tree)
        self.console.print("")

    def _render_systemd_telemetry(
        self, task: str, host: str, duration: str, payload: Dict[str, Any]
    ) -> None:
        """
        Parses systemd service states, emitting a highly abstract, compact status dashboard.
        """
        status_data = payload.get("status", {})
        state = payload.get("state", status_data.get("ActiveState", "unknown"))

        # Deterministically map systemd active states to Unicode iconography
        if state in ("started", "active"):
            icon, color = "✔️ RUNNING", "bold green"
        elif state in ("stopped", "inactive"):
            icon, color = "⏸️ INACTIVE", "bold yellow"
        elif state == "failed":
            icon, color = "❌ FAILED", "bold red"
        else:
            icon, color = "❓ UNKNOWN", "dim white"

        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", justify="right")
        table.add_column("Value", style=color)

        table.add_row("Daemon Target:", payload.get("name", "Unknown Unit"))
        table.add_row("Active State:", icon)

        # Verify Boot and SysV linking states
        if "enabled" in payload:
            is_enabled = payload["enabled"]
            enabled_text = "🔗 Enabled (Symlinked to Target)" if is_enabled else "🛑 Disabled"
            table.add_row("Boot State:", enabled_text)

        if "masked" in payload:
            is_masked = payload["masked"]
            if is_masked:
                table.add_row("Mask State:", "🚫 Masked (Linked to /dev/null)")

        panel = Panel(
            table,
            title=f"⚙️ Systemd Transition | {host} | {task} ({duration})",
            border_style="blue",
            expand=False,
        )
        self.console.print("")
        self.console.print(panel)
        self.console.print("")

    @staticmethod
    def _is_probe_task(task_name: str, task: Task, payload: Dict[str, Any]) -> bool:
        """
        Determine if the executed task represents an environment or capability probe.
        """
        task_lower = task_name.lower()
        task_tags = getattr(task, "tags", []) or []

        if "probe" in task_tags or "probe" in task_lower:
            return True
        if task_lower.startswith("inspect ") or " inspect " in task_lower:
            return True
        if getattr(task, "action", "") == "ansible.builtin.stat" and "stat" in payload:
            return True

        return False

    @staticmethod
    def _translate_probe_command(task_name: str, cmd_data: Any, stat_data: Dict[str, Any]) -> str:
        """
        Translate raw capability probe commands and multi-line script blocks into
        clean, human-readable natural language descriptions.
        """
        if stat_data:
            path = stat_data.get("path")
            if path:
                return f"Checking filesystem existence and attributes for '{path}'"
            return "Inspecting filesystem target attributes"

        clean_task = task_name.split(" : ")[-1].strip()

        if not cmd_data:
            return clean_task

        if isinstance(cmd_data, list):
            cmd_str = " ".join(str(c) for c in cmd_data).strip()
        else:
            cmd_str = str(cmd_data).strip()

        is_multiline_script = "\n" in cmd_str or (
            ("sh -c" in cmd_str or "bash -c" in cmd_str) and len(cmd_str) > 80
        )

        # Domain Heuristics: Hardware acceleration & GPU sysfs discovery
        if "vulkaninfo" in cmd_str or "vulkan" in clean_task.lower():
            return (
                "Probing Vulkan device drivers, DRI render nodes (/dev/dri/renderD*), "
                "and GPU acceleration"
            )
        if "nvidia-smi" in cmd_str or "/dev/nvidia" in cmd_str or "cuda" in clean_task.lower():
            return "Probing NVIDIA driver stack, device nodes (/dev/nvidia*), and CUDA acceleration"
        if "/sys/bus/pci/devices" in cmd_str or "gpu vendor" in clean_task.lower():
            return (
                "Scanning PCI sysfs bus (/sys/bus/pci/devices) for GPU display vendor identifiers"
            )
        if "MemTotal" in cmd_str or "/proc/meminfo" in cmd_str:
            return "Reading total system memory capacity from /proc/meminfo"
        if cmd_str == "nproc" or "nproc" in clean_task.lower():
            return "Querying available processing cores via nproc"
        if "cpulimit" in cmd_str or "cpulimit" in clean_task.lower():
            return "Checking for 'cpulimit' utility availability in system PATH"

        # Binary discovery (which / command -v)
        which_match = re.search(r"(?:which|command -v)\s+([^\s;&|]+)", cmd_str)
        if which_match:
            target_bin = which_match.group(1).strip("'\"")
            return f"Locating '{target_bin}' executable in system PATH"

        # Process table discovery (pgrep)
        pgrep_match = re.search(r"pgrep(?:\s+-[a-zA-Z]+)*\s+([^\s;&|]+)", cmd_str)
        if pgrep_match:
            proc_name = pgrep_match.group(1).strip("'\"")
            return f"Inspecting process table for running '{proc_name}' instances"

        # Version discovery (<bin> --version / <bin> version / <bin> -v)
        ver_match = re.search(r"([^\s;&|]+)\s+(?:--version|-v|version)\b", cmd_str)
        if ver_match:
            bin_name = os.path.basename(ver_match.group(1).strip("'\""))
            return f"Querying installed release version of '{bin_name}'"

        # DNF repository discovery
        if "dnf info" in cmd_str:
            pkg_match = re.search(r"dnf info\s+([^\s;&|]+)", cmd_str)
            pkg = pkg_match.group(1) if pkg_match else "package"
            return f"Querying DNF repository metadata for '{pkg}'"

        # Flatpak discovery
        if "flatpak list" in cmd_str:
            return "Enumerating installed Flatpak applications"

        # Mount options
        if "findmnt" in cmd_str:
            target_match = re.search(r"--target\s+([^\s;&|]+)", cmd_str)
            target = target_match.group(1) if target_match else "filesystem"
            return f"Inspecting mount options and execution flags for {target}"

        # Systemd state
        if "systemctl get-default" in cmd_str:
            return "Querying default systemd boot target"
        if "systemctl is-active" in cmd_str:
            svc_match = re.search(r"systemctl is-active\s+([^\s;&|]+)", cmd_str)
            svc = svc_match.group(1) if svc_match else "service"
            return f"Checking active runtime state of systemd unit '{svc}'"

        # Multi-line script fallback
        if is_multiline_script:
            m = re.match(r"(?i)probe\s+(?:for\s+|the\s+)?(.*)", clean_task)
            if m:
                return f"Evaluating {m.group(1)}"
            return f"Executing system capability probe for {clean_task}"

        # Single-line command fallback
        if len(cmd_str) <= 60:
            return f"Querying command: {cmd_str}"
        return f"Evaluating {clean_task}"

    def _render_probe_telemetry(
        self, task: str, host: str, duration: str, payload: Dict[str, Any]
    ) -> None:
        """
        Parses hardware and capability probe results, rendering a compact,
        high-contrast telemetry panel displaying target queries, verdicts, and discovered state.
        """
        table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
        table.add_column("Key", style="bold cyan", justify="right")
        table.add_column("Val")

        stat_data = payload.get("stat", {})
        cmd_data = payload.get("cmd") or payload.get("argv")
        rc = payload.get("rc")

        description = self._translate_probe_command(task, cmd_data, stat_data)
        table.add_row("Query Target:", f"[bold white]{description}[/]")

        if cmd_data:
            if isinstance(cmd_data, list):
                cmd_str = " ".join(str(c) for c in cmd_data).strip()
            else:
                cmd_str = str(cmd_data).strip()

            is_multiline = "\n" in cmd_str or (
                ("sh -c" in cmd_str or "bash -c" in cmd_str) and len(cmd_str) > 80
            )

            if not is_multiline and len(cmd_str) <= 70:
                table.add_row("Command:", f"[dim cyan]{cmd_str}[/]")
            elif is_multiline:
                table.add_row("Command:", "[dim](Hardware probe script)[/]")

            stdout = (payload.get("stdout") or "").strip()
            stderr = (payload.get("stderr") or "").strip()

            if rc == 0:
                if stdout:
                    lines = stdout.splitlines()
                    table.add_row("Verdict:", "[bold green]🟢 FOUND / AVAILABLE[/]")
                    if len(lines) == 1:
                        table.add_row("Discovered:", f"[bold white]{lines[0]}[/]")
                    else:
                        preview = "\n".join(f"  [dim]│[/] {line}" for line in lines[:5])
                        if len(lines) > 5:
                            preview += f"\n  [dim]│ ... (+{len(lines) - 5} more lines)[/]"
                        table.add_row("Discovered:", f"[bold white]\n{preview}[/]")
                else:
                    table.add_row("Verdict:", "[bold green]🟢 MATCHED / ACTIVE[/]")
            else:
                table.add_row(
                    "Verdict:", f"[dim yellow]⚪ ABSENT / NOT FOUND[/] [dim](exit code {rc})[/]"
                )
                if stderr:
                    table.add_row("Stderr:", f"[dim red]{stderr.splitlines()[0]}[/]")
        elif stat_data:
            exists = stat_data.get("exists", False)
            if exists:
                file_type = "directory" if stat_data.get("isdir") else "file"
                mode = stat_data.get("mode", "unknown")
                table.add_row("Verdict:", "[bold green]🟢 PRESENT[/]")
                table.add_row("Attributes:", f"[bold white]{file_type} (mode: {mode})[/]")
            else:
                table.add_row("Verdict:", "[dim yellow]⚪ ABSENT[/]")
        else:
            status_text = "CHANGED" if payload.get("changed", False) else "OK"
            table.add_row("Status:", f"[bold green]🟢 {status_text}[/]")

        panel = Panel(
            table,
            title=(
                f"🔍 [bold cyan]Capability Probe[/] │ [bold white]{host}[/] │ "
                f"[white]{task}[/] [dim cyan]({duration})[/]"
            ),
            border_style="cyan",
            expand=False,
        )
        self.console.print("")
        self.console.print(panel)
        self.console.print("")

    def _render_generic_success(
        self, task: str, host: str, duration: str, status: str, changed: bool = False
    ) -> None:
        """
        Fallback renderer enforcing clean, single-line telemetry for modules
        without specialized TUI implementations.
        """
        color = "yellow" if changed else "green"
        self.console.print(f"[{color}][{status}][/] {host} | {task} (Execution: {duration})")

    def v2_playbook_on_stats(self, stats: Any) -> None:
        """
        Render a high-contrast structural recap table upon playbook completion.
        """
        hosts = sorted(stats.processed.keys())
        if not hosts:
            return

        table = Table(
            title="📊 Play Recap",
            show_header=True,
            header_style="bold cyan",
            expand=False,
        )
        table.add_column("Target Host", style="bold white")
        table.add_column("OK", justify="right")
        table.add_column("Changed", justify="right")
        table.add_column("Unreachable", justify="right")
        table.add_column("Failed", justify="right")
        table.add_column("Skipped", justify="right")
        table.add_column("Rescued", justify="right")
        table.add_column("Ignored", justify="right")

        for host in hosts:
            summary = stats.summarize(host)
            unreachable_style = "bold red" if summary["unreachable"] > 0 else "dim white"
            failed_style = "bold red" if summary["failures"] > 0 else "dim white"
            changed_style = "bold yellow" if summary["changed"] > 0 else "dim white"
            ok_style = "bold green" if summary["ok"] > 0 else "dim white"
            skipped_style = "cyan" if summary["skipped"] > 0 else "dim white"
            rescued_style = "magenta" if summary["rescued"] > 0 else "dim white"
            ignored_style = "blue" if summary["ignored"] > 0 else "dim white"

            table.add_row(
                host,
                f"[{ok_style}]{summary['ok']}[/]",
                f"[{changed_style}]{summary['changed']}[/]",
                f"[{unreachable_style}]{summary['unreachable']}[/]",
                f"[{failed_style}]{summary['failures']}[/]",
                f"[{skipped_style}]{summary['skipped']}[/]",
                f"[{rescued_style}]{summary['rescued']}[/]",
                f"[{ignored_style}]{summary['ignored']}[/]",
            )

        self.console.print("\n")
        self.console.print(table)
        self.console.print("\n")
