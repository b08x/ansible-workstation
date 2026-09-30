"""Shared fixtures for the remediation pipeline tests.

Puts ``plugins/callback_utils`` on ``sys.path`` so the store, signatures,
guard and CLI import by their bare names, exactly the way the callback and
CLI do at runtime.
"""

from __future__ import absolute_import, division, print_function

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
UTILS_DIR = REPO_ROOT / "plugins" / "callback_utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ollama: requires a live Ollama daemon with embeddinggemma:latest"
    )


def load_module_file(name, relative_path):
    """Import a repo file that is not part of a package (modules, actions)."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubEmbedder:
    """Deterministic bag-of-words embedder standing in for Ollama.

    Texts that share words land close in cosine space; the model name is
    recorded per incident exactly like the real one.
    """

    def __init__(self, host=None, model="stub-embed", timeout=0.0):
        self.host = host
        self.model = model
        self.timeout = timeout

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text, dim=8):
        vector = [0.0] * dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vector[hash(word) % dim] += 1.0
        return vector


@pytest.fixture
def stub_embedder():
    return StubEmbedder()
