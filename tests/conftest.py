"""Shared fixtures: run every test against an empty, temporary data directory."""

import os
import tempfile

# Ignore any local config.json so tests always see the defaults
os.environ["HOMEBASE_CONFIG"] = os.path.join(tempfile.gettempdir(), "homebase-test-missing.json")

import pytest

from homebase import storage


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield tmp_path
