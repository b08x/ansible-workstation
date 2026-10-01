"""fact-11: the guard rejects every volume-destroying pattern it must."""

from __future__ import absolute_import, division, print_function

import pytest
from remediation_guard import scan_playbook

BENIGN = """
- name: Recreate the langfuse pod
  hosts: all
  tasks:
    - name: Stop the pod without touching volumes
      ansible.builtin.command:
        cmd: podman pod stop langfuse
      changed_when: true
    - name: Ensure the web container runs
      containers.podman.podman_container:
        name: langfuse-web
        image: docker.io/langfuse/langfuse:latest
        state: started
        recreate: true
"""

FORBIDDEN = [
    (
        "podman_volume module state absent",
        """
- name: T1
  hosts: all
  tasks:
    - name: Remove the volume
      containers.podman.podman_volume:
        name: langfuse_pgdata
        state: absent
""",
    ),
    (
        "podman volume rm",
        """
- name: T2
  hosts: all
  tasks:
    - name: Shell rm
      ansible.builtin.shell: podman volume rm langfuse_pgdata
""",
    ),
    (
        "podman volume prune",
        """
- name: T3
  hosts: all
  tasks:
    - name: Shell prune
      ansible.builtin.shell: podman volume prune --force
""",
    ),
    (
        "podman system prune --volumes",
        """
- name: T4
  hosts: all
  tasks:
    - name: System prune
      ansible.builtin.command:
        cmd: podman system prune --volumes --force
""",
    ),
    (
        "podman pod rm -v",
        """
- name: T5
  hosts: all
  tasks:
    - name: Pod rm with volumes
      ansible.builtin.command:
        argv: [podman, pod, rm, -v, langfuse]
""",
    ),
    (
        "podman rm -v",
        """
- name: T6
  hosts: all
  tasks:
    - name: Container rm with volumes
      ansible.builtin.command: podman rm -v langfuse-web
""",
    ),
    (
        "file state absent on volume data",
        """
- name: T7
  hosts: all
  tasks:
    - name: Delete volume data
      ansible.builtin.file:
        path: /home/b08x/.local/share/containers/storage/volumes/langfuse_pgdata/_data
        state: absent
""",
    ),
    (
        "rm -rf under containers storage volumes",
        """
- name: T8
  hosts: all
  tasks:
    - name: Shell rm -rf
      ansible.builtin.shell: >
        rm -rf /home/b08x/.local/share/containers/storage/volumes/langfuse_pgdata
""",
    ),
    (
        "podman pod rm --volumes",
        """
- name: T9
  hosts: all
  tasks:
    - name: Pod rm with long flag
      ansible.builtin.command: podman pod rm --volumes langfuse
""",
    ),
    # Bypasses found in the 2026-09-30 review; each passed the original guard.
    (
        "podman rm with combined short flags -fv",
        """
- name: T10
  hosts: all
  tasks:
    - name: Force rm with volumes
      ansible.builtin.command: podman rm -fv langfuse-db
""",
    ),
    (
        "podman container rm -v",
        """
- name: T11
  hosts: all
  tasks:
    - name: Long-form container rm
      ansible.builtin.command: podman container rm -v langfuse-db
""",
    ),
    (
        "podman system reset",
        """
- name: T12
  hosts: all
  tasks:
    - name: Reset podman storage
      ansible.builtin.command: podman system reset --force
""",
    ),
    (
        "podman_prune module with volume true",
        """
- name: T13
  hosts: all
  tasks:
    - name: Prune volumes
      containers.podman.podman_prune:
        volume: true
""",
    ),
    (
        "podman-compose down -v",
        """
- name: T14
  hosts: all
  tasks:
    - name: Compose down with volumes
      ansible.builtin.command: podman-compose down -v
""",
    ),
    (
        "podman compose down --volumes",
        """
- name: T15
  hosts: all
  tasks:
    - name: Compose down with volumes
      ansible.builtin.command: podman compose down --volumes
""",
    ),
    (
        "rm -rf on the containers storage root",
        """
- name: T16
  hosts: all
  tasks:
    - name: Wipe storage
      ansible.builtin.command: rm -rf /home/u/.local/share/containers/storage
""",
    ),
    (
        "rm -rf on the user's home",
        """
- name: T17
  hosts: all
  tasks:
    - name: Wipe home
      ansible.builtin.shell: rm -rf ~/.local/share
""",
    ),
    (
        "rm -rf through a play variable",
        """
- name: T18
  hosts: all
  vars:
    pgdata: /home/u/.local/share/containers/storage/volumes/langfuse_pg
  tasks:
    - name: Remove through a var
      ansible.builtin.command: rm -rf {{ pgdata }}
""",
    ),
    (
        "file state absent through a play variable",
        """
- name: T19
  hosts: all
  vars:
    pgdata: /home/u/.local/share/containers/storage/volumes/langfuse_pg
  tasks:
    - name: Remove through a var
      ansible.builtin.file:
        path: "{{ pgdata }}"
        state: absent
""",
    ),
    (
        "file state absent on an unresolvable loop item",
        """
- name: T20
  hosts: all
  tasks:
    - name: Remove listed paths
      ansible.builtin.file:
        path: "{{ item }}"
        state: absent
      loop: "{{ stale_paths }}"
""",
    ),
    (
        "find -delete under volumes",
        """
- name: T21
  hosts: all
  tasks:
    - name: Find and delete
      ansible.builtin.shell: find /var/lib/containers/storage/volumes -name '*.db' -delete
""",
    ),
]

BENIGN_CASES = [
    ("podman pod rm -f without volumes", "ansible.builtin.command: podman pod rm -f langfuse"),
    ("podman rm -f without volumes", "ansible.builtin.command: podman rm -f langfuse-web"),
    (
        "-v in a later command of the same line",
        "ansible.builtin.shell: podman rm langfuse-web && journalctl -v | grep -v noise",
    ),
    ("podman_prune of images only", "containers.podman.podman_prune:\n        image: true"),
    ("rm of a temp file", "ansible.builtin.command: rm -f /tmp/langfuse.lock"),
    ("podman compose down without volumes", "ansible.builtin.command: podman compose down"),
    (
        "podman rm of a templated container name",
        "ansible.builtin.command: podman rm -f {{ item }}\n      loop: [langfuse-web]",
    ),
    (
        "stale shm under overlay-containers",
        "ansible.builtin.command: rm -rf "
        "/home/u/.local/share/containers/storage/overlay-containers/abc/userdata/shm",
    ),
]


@pytest.mark.parametrize(
    "command",
    [
        "sudo rm -rf /var/lib/containers/storage",
        "ls -d /var/lib/containers/storage/volumes/* | xargs rm -rf",
        "/usr/bin/rm -r ~/.local/share/containers",
    ],
)
def test_rm_in_command_position_rejected(command):
    playbook = f"""
- name: T
  hosts: all
  tasks:
    - name: Delete
      ansible.builtin.shell: {command}
"""
    assert scan_playbook(playbook), command


@pytest.mark.parametrize("label,task", BENIGN_CASES, ids=[b[0] for b in BENIGN_CASES])
def test_benign_commands_pass(label, task):
    playbook = f"""
- name: Benign
  hosts: all
  tasks:
    - name: {label}
      {task}
"""
    assert scan_playbook(playbook) == [], label


def test_file_absent_through_resolvable_var_outside_volumes_passes():
    playbook = """
- name: Cleanup
  hosts: all
  vars:
    lockfile: /tmp/langfuse.lock
  tasks:
    - name: Remove stale lock
      ansible.builtin.file:
        path: "{{ lockfile }}"
        state: absent
"""
    assert scan_playbook(playbook) == []


def test_benign_playbook_passes():
    assert scan_playbook(BENIGN) == []


@pytest.mark.parametrize("label,playbook", FORBIDDEN, ids=[f[0] for f in FORBIDDEN])
def test_forbidden_patterns_rejected(label, playbook):
    violations = scan_playbook(playbook)
    assert violations, f"guard accepted a playbook that {label}"


def test_podman_container_recreate_passes():
    playbook = """
- name: Recreate
  hosts: all
  tasks:
    - name: Recreate container
      containers.podman.podman_container:
        name: langfuse-web
        state: started
        recreate: true
"""
    assert scan_playbook(playbook) == []


def test_file_absent_outside_volumes_passes():
    playbook = """
- name: Cleanup
  hosts: all
  tasks:
    - name: Remove stale lock
      ansible.builtin.file:
        path: /tmp/langfuse.lock
        state: absent
"""
    assert scan_playbook(playbook) == []


def test_invalid_yaml_raises():
    with pytest.raises(ValueError):
        scan_playbook("tasks: [unclosed")


def test_non_playbook_document_raises():
    with pytest.raises(ValueError):
        scan_playbook("just a string")


def test_benign_podman_rm_without_v_flag_passes():
    playbook = """
- name: Remove a container without volumes
  hosts: all
  tasks:
    - name: rm container
      ansible.builtin.command: podman rm langfuse-web
"""
    assert scan_playbook(playbook) == []


# -- Outage guard: prove the replacement before removing what works ----------

from remediation_guard import scan_outage  # noqa: E402

# The draft that took ollama down on tinybot on 2026-09-30 (inc-dfc1e47fdb5f).
OUTAGE_DRAFT = """
- name: Remediate ollama container shm mount failure
  hosts: all
  become: false
  gather_facts: false
  tasks:
    - name: Remove existing ollama container
      containers.podman.podman_container:
        name: ollama
        state: absent
    - name: Create and start ollama container with corrected shm size
      containers.podman.podman_container:
        name: ollama
        image: docker.io/ollama/ollama:latest
        state: started
        shm_size: 128m
"""

# The order used to recreate ollama by hand afterwards.
SAFE_REPLACEMENT = """
- name: Replace the ollama container safely
  hosts: all
  become: false
  gather_facts: false
  tasks:
    - name: Test-run the image before touching the running container
      ansible.builtin.command: podman run --rm docker.io/ollama/ollama:latest --version
      changed_when: false
    - name: Stop the current container
      ansible.builtin.command: podman stop ollama
      changed_when: true
    - name: Keep the current container under another name
      ansible.builtin.command: podman rename ollama ollama-old
      changed_when: true
    - name: Create the replacement
      containers.podman.podman_container:
        name: ollama
        image: docker.io/ollama/ollama:latest
        state: started
    - name: Check the replacement answers
      ansible.builtin.uri:
        url: http://localhost:11434/api/version
    - name: Remove the old container
      containers.podman.podman_container:
        name: ollama-old
        state: absent
"""


def _play(*tasks):
    body = "\n".join(tasks)
    return f"""
- name: P
  hosts: all
  tasks:
{body}
"""


def test_outage_draft_is_rejected():
    violations = scan_outage(OUTAGE_DRAFT)
    assert violations
    assert "Remove existing ollama container" in violations[0]
    assert "podman run --rm" in violations[0]


def test_safe_replacement_passes():
    assert scan_outage(SAFE_REPLACEMENT) == []


def test_recreate_true_without_preflight_is_rejected():
    playbook = _play(
        "    - name: Recreate\n"
        "      containers.podman.podman_container:\n"
        "        name: ollama\n"
        "        image: docker.io/ollama/ollama:latest\n"
        "        state: started\n"
        "        recreate: true"
    )
    assert "recreates container ollama" in scan_outage(playbook)[0]


@pytest.mark.parametrize(
    "task",
    [
        "ansible.builtin.command: podman rm -f ollama",
        "ansible.builtin.command: podman container rm ollama",
        "ansible.builtin.command: podman pod rm -f langfuse",
        "ansible.builtin.command: podman-compose down",
        "containers.podman.podman_pod:\n        name: langfuse\n        state: absent",
        "containers.podman.podman_pod:\n        name: langfuse\n        state: started\n        recreate: true",
    ],
)
def test_removal_without_preflight_is_rejected(task):
    assert scan_outage(_play(f"    - name: T\n      {task}")), task


def test_preflight_after_removal_does_not_count():
    playbook = _play(
        "    - name: Remove\n      ansible.builtin.command: podman rm -f ollama",
        "    - name: Test-run too late\n      ansible.builtin.command: podman run --rm img true",
    )
    assert scan_outage(playbook)


def test_preflight_inside_an_earlier_block_counts():
    playbook = _play(
        "    - name: Prove\n      block:\n"
        "        - name: Test-run\n          ansible.builtin.command: podman run --rm img true",
        "    - name: Remove\n      ansible.builtin.command: podman rm -f ollama",
    )
    assert scan_outage(playbook) == []


def test_podman_container_rm_true_counts_as_preflight():
    playbook = _play(
        "    - name: Test-run\n      containers.podman.podman_container:\n"
        "        name: probe\n        image: img\n        command: 'true'\n"
        "        rm: true\n        detach: false\n        state: started",
        "    - name: Remove\n      ansible.builtin.command: podman rm -f ollama",
    )
    assert scan_outage(playbook) == []


def test_stop_start_and_rename_are_not_removals():
    playbook = _play(
        "    - name: Stop\n      ansible.builtin.command: podman stop ollama",
        "    - name: Rename\n      ansible.builtin.command: podman rename ollama ollama-old",
        "    - name: Start\n      containers.podman.podman_container:\n        name: ollama\n        state: started",
    )
    assert scan_outage(playbook) == []


def test_task_name_mentioning_preflight_does_not_count():
    playbook = _play(
        "    - name: podman run --rm would be nice\n      ansible.builtin.debug:\n        msg: hi",
        "    - name: Remove\n      ansible.builtin.command: podman rm -f ollama",
    )
    assert scan_outage(playbook)
