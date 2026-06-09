"""OpenAPI contract checks for the bridge endpoints the client consumes (CR-0008).

These tests run against a *captured* slice of the bridge ``GET /v1/openapi.json``
(``tests/fixtures/bridge_openapi_contract.json``) -- never the live bridge, per the
TDD rule. Refresh the fixture from the live spec when the bridge baseline moves; a
consumed endpoint disappearing from the spec then fails here in CI instead of at
runtime on a live install.
"""

from __future__ import annotations

import json
import pathlib

import pytest

FIXTURE = pathlib.Path("tests/fixtures/bridge_openapi_contract.json")

# The (method, path) pairs BridgeClient calls. Keep in sync with client.py.
CONSUMED = [
    "GET /health",
    "GET /v1/health",
    "GET /v1/discovery",
    "GET /v1/agent-context",
    "POST /v1/chat/completions",
    "POST /v1/broadcast",
    "POST /v1/tools/invoke",
    "POST /v1/webhooks",
    "GET /v1/agents/{id}/usage",
    "POST /v1/agents/{id}/memory",
    "GET /v1/agents/{id}/memory",
    "GET /v1/doctor",
]


@pytest.fixture(scope="module")
def contract() -> dict:
    return json.loads(FIXTURE.read_text())


def test_all_consumed_endpoints_present(contract):
    """Every endpoint the client relies on exists in the captured bridge spec."""
    present = contract["consumed_endpoints_present"]
    missing = [ep for ep in CONSUMED if not present.get(ep)]
    assert not missing, f"consumed endpoints absent from the bridge OpenAPI: {missing}"


def test_consumed_list_matches_fixture(contract):
    """The client's consumed list and the captured fixture do not drift apart."""
    assert set(CONSUMED) == set(contract["consumed_endpoints_present"])


def test_chat_completions_accepts_messages(contract):
    """The core chat field the client always sends is part of the request schema."""
    assert "messages" in contract["chat_completions_request_fields"]


def test_consumed_paths_exist_in_full_spec(contract):
    """Each consumed path is one the spec actually declares (catches renames)."""
    all_paths = set(contract["all_paths"])
    for ep in CONSUMED:
        path = ep.split(" ", 1)[1]
        assert path in all_paths, f"{path} not in the bridge OpenAPI paths"
