"""Integration tests run against a deployed stack, so they need the network the unit suite refuses.
They're skipped unless `EVAL_API_URL` names the stack's API (CI never sets it)."""

from __future__ import annotations

import os

import pytest

API_URL = os.environ.get("EVAL_API_URL", "").rstrip("/")


@pytest.fixture(autouse=True)
def no_network():
    """Overrides the unit suite's network guard: these tests exist to reach the deployed API."""
    yield


def pytest_collection_modifyitems(items):
    skip = pytest.mark.skip(reason="set EVAL_API_URL to the deployed API to run integration tests")
    for item in items:
        if "integration" in item.nodeid.replace("\\", "/").split("/"):
            item.add_marker(pytest.mark.integration)
            if not API_URL:
                item.add_marker(skip)
