"""Tests für den MCP-Tool-Loader: tolerant gegen Ausfälle, Tools bei Erfolg."""

from __future__ import annotations

import contextlib

import pytest

from agent_runtime import mcp_tools


@pytest.mark.asyncio
async def test_session_yields_empty_on_error(monkeypatch):
    import autogen_ext.tools.mcp as m

    def boom(params):
        raise RuntimeError("server weg")

    monkeypatch.setattr(m, "create_mcp_server_session", boom)
    async with mcp_tools.load_mcp_tools_session("http://x/mcp", "streamable_http") as tools:
        assert tools == []


@pytest.mark.asyncio
async def test_session_yields_tools_on_success(monkeypatch):
    import autogen_ext.tools.mcp as m

    @contextlib.asynccontextmanager
    async def fake_session(params):
        class _S:
            async def initialize(self):
                return None

        yield _S()

    async def fake_tools(server_params=None, session=None):
        return ["tool_a", "tool_b"]

    monkeypatch.setattr(m, "create_mcp_server_session", fake_session)
    monkeypatch.setattr(m, "mcp_server_tools", fake_tools)
    async with mcp_tools.load_mcp_tools_session("http://x/mcp", "streamable_http") as tools:
        assert tools == ["tool_a", "tool_b"]


def test_params_passes_headers_streamable(monkeypatch):
    captured = {}

    class FakeStreamable:
        def __init__(self, **kw):
            captured.update(kw)

    class FakeSse:
        def __init__(self, **kw):
            captured.update(kw)

    import autogen_ext.tools.mcp as mcp_mod

    monkeypatch.setattr(mcp_mod, "StreamableHttpServerParams", FakeStreamable)
    monkeypatch.setattr(mcp_mod, "SseServerParams", FakeSse)
    mcp_tools._params("https://x/mcp", "streamable_http", {"Authorization": "Bearer t"})
    assert captured["url"] == "https://x/mcp"
    assert captured["headers"] == {"Authorization": "Bearer t"}


def test_params_no_headers_when_none(monkeypatch):
    captured = {}

    class FakeStreamable:
        def __init__(self, **kw):
            captured.update(kw)

    import autogen_ext.tools.mcp as mcp_mod

    monkeypatch.setattr(mcp_mod, "StreamableHttpServerParams", FakeStreamable)
    mcp_tools._params("https://x/mcp", "streamable_http", None)
    assert captured.get("headers") is None


def test_sanitize_collapses_type_unions():
    from agent_runtime.mcp_tools import _sanitize_json_schema
    sch = {"type": "object", "properties": {
        "x": {"type": ["string", "null"]},
        "y": {"type": "array", "items": {"type": ["string", "number"]}},
    }}
    out = _sanitize_json_schema(sch)
    assert out["properties"]["x"]["type"] == "string"
    assert out["properties"]["y"]["items"]["type"] == "string"


def test_schema_patch_makes_type_unions_loadable():
    from agent_runtime.mcp_tools import _ensure_schema_patch
    _ensure_schema_patch()
    from autogen_ext.tools.mcp import _base
    m = _base.schema_to_pydantic_model({"type": "object", "properties": {"x": {"type": ["string", "null"]}}})
    assert "x" in m.model_fields
