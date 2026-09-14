#!/usr/bin/env python3
"""Render fedora-workstation.toml.j2 with test pins and validate the TOML."""
import json
import sys

try:
    import tomllib
except ImportError:
    tomllib = None

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    print("SKIP: jinja2 not available")
    sys.exit(0)

TPL = (
    "collections/ansible_collections/b08x/rhel_builder/roles/"
    "osbuild/templates/fedora-workstation.toml.j2"
)

ctx = {
    "blueprint_name": "pin-test",
    "blueprint_description": "pin render test",
    "blueprint_version": "1.0.0",
    "osbuild_distro": "fedora-43",
    "osbuild_components": ["base", "nvidia"],
    "osbuild_component_defs": {
        "base": {
            "packages": ["bash", "kernel", "python3"],
            "blueprint_groups": ["base"],
        },
        "nvidia": {
            "packages": ["cuda-toolkit", "nvidia-driver"],
            "kernel_args": "nvidia-drm.modeset=1",
            "services": ["nvidia-persistenced"],
        },
    },
    "osbuild_extra_packages": ["zsh"],
    "osbuild_package_pins": {"python3": "3.11.*", "cuda-toolkit": "13-4.*"},
    "osbuild_timezone": "America/New_York",
    "osbuild_locale": "en_US.UTF-8",
    "osbuild_keyboard": "us",
    "osbuild_user_name": "test",
    "osbuild_user_description": "Test User",
    "osbuild_user_password": "$6$testhash",
    "osbuild_user_groups": ["wheel"],
}

env = Environment(
    loader=FileSystemLoader(
        "collections/ansible_collections/b08x/rhel_builder/"
        "roles/osbuild/templates"  # noqa: E501
    ),
    undefined=StrictUndefined,
)
env.filters["to_json"] = json.dumps  # noqa: E501
ctx["ansible_managed"] = "Ansible managed (test render)"

out = env.get_template("fedora-workstation.toml.j2").render(**ctx)
pins = [line for line in out.splitlines() if line.startswith("version")]
print("rendered version lines:")
for line in pins:
    print("  ", line)

expected = {
    'version = "3.11.*"',  # python3 pinned
    'version = "13-4.*"',  # cuda-toolkit pinned
    'version = "*"',  # everything else
}
got = set(pins)
assert expected <= got, f"missing expected pins: {expected - got}"
assert 'version = "1.0.0"' in got  # blueprint version header

if tomllib:
    data = tomllib.loads(out)
    vers = {p["name"]: p["version"] for p in data["packages"]}
    assert vers["python3"] == "3.11.*", vers
    assert vers["cuda-toolkit"] == "13-4.*", vers
    assert vers["zsh"] == "*", vers
    print(
        "TOML valid; pinned versions verified:",
        vers["python3"],
        vers["cuda-toolkit"],
        "zsh ->",
        vers["zsh"],
    )
print("PASS")
