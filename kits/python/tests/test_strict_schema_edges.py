"""Schema-edge coverage for StrictArgsMiddleware, driven at the middleware seam directly
(a full server cannot easily produce a no-`properties` or malformed-`properties` schema).

Covers the tools/list advertise branches — setdefault-not-force, skip-no-properties, the
BaseModel result form — and the tools/call malformed-schema branch: `properties` PRESENT
but NOT a map is UNINTROSPECTABLE and stays PERMISSIVE (it must not refuse every argument).
"""

from types import SimpleNamespace

import pytest

from ironmcp.strict import StrictArgsMiddleware


async def _run(mw, ctx, result):
    async def call_next(_ctx):
        return result

    return await mw(ctx, call_next)


# --- tools/list advertise branches -----------------------------------------------------


@pytest.mark.asyncio
async def test_list_stamps_closed_on_an_introspectable_schema():
    result = {"tools": [{"inputSchema": {"type": "object", "properties": {"a": {}}}}]}
    await _run(StrictArgsMiddleware(), SimpleNamespace(method="tools/list", params=None), result)
    assert result["tools"][0]["inputSchema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_list_setdefault_not_force_preserves_a_declared_true():
    """A tool that pre-declares additionalProperties:true STAYS true after tools/list —
    setdefault, never force. The author's opt-out survives advertisement."""
    result = {
        "tools": [
            {"inputSchema": {"type": "object", "properties": {"a": {}}, "additionalProperties": True}}
        ]
    }
    await _run(StrictArgsMiddleware(), SimpleNamespace(method="tools/list", params=None), result)
    assert result["tools"][0]["inputSchema"]["additionalProperties"] is True


@pytest.mark.asyncio
async def test_list_skips_a_schema_with_no_properties_block():
    """A schema with type:object but NO properties key is left permissive — stamping
    'accepts nothing' there would contradict the runtime (absent property set = permissive)."""
    result = {"tools": [{"inputSchema": {"type": "object"}}]}
    await _run(StrictArgsMiddleware(), SimpleNamespace(method="tools/list", params=None), result)
    assert "additionalProperties" not in result["tools"][0]["inputSchema"]


@pytest.mark.asyncio
async def test_list_skips_a_malformed_properties_value():
    """properties PRESENT but not a map (a string) is malformed/uninstrospectable — do NOT
    stamp additionalProperties:false on it."""
    result = {"tools": [{"inputSchema": {"type": "object", "properties": "not-a-map"}}]}
    await _run(StrictArgsMiddleware(), SimpleNamespace(method="tools/list", params=None), result)
    assert "additionalProperties" not in result["tools"][0]["inputSchema"]


@pytest.mark.asyncio
async def test_list_handles_the_basemodel_result_form():
    """For robustness the advertise path also accepts a non-dict (BaseModel-like) result whose
    .tools items expose .input_schema, not a serialized dict."""
    schema = {"type": "object", "properties": {"a": {}}}
    tool = SimpleNamespace(input_schema=schema)
    result = SimpleNamespace(tools=[tool])
    await _run(StrictArgsMiddleware(), SimpleNamespace(method="tools/list", params=None), result)
    assert schema["additionalProperties"] is False


# --- tools/call malformed-schema branch: PERMISSIVE, not refuse-all ---------------------


class _FakeTool:
    def __init__(self, parameters):
        self.parameters = parameters


class _FakeServer:
    def __init__(self, tool):
        self._tool_manager = SimpleNamespace(get_tool=lambda _name: tool)


_SENTINEL = object()


async def _call(schema, arguments):
    mw = StrictArgsMiddleware(server=_FakeServer(_FakeTool(schema)))
    ctx = SimpleNamespace(method="tools/call", params={"name": "echo", "arguments": arguments})

    reached = {"v": False}

    async def call_next(_ctx):
        reached["v"] = True
        return _SENTINEL

    out = await mw(ctx, call_next)
    return out, reached["v"]


@pytest.mark.asyncio
async def test_call_malformed_properties_is_permissive_not_refuse_all():
    """properties is a string, not a map: the accepted set is unknowable, so the guard MUST
    pass the call through (permissive) rather than refuse the argument. Without the isinstance
    gate, set('not-a-map') would be treated as the accepted keys and refuse 'x'."""
    out, reached = await _call({"type": "object", "properties": "not-a-map"}, {"x": 1})
    assert reached is True  # call_next ran -> permissive passthrough
    assert out is _SENTINEL


@pytest.mark.asyncio
async def test_call_well_formed_schema_still_refuses_unknown_control():
    """Positive control: a proper properties map DOES refuse the unknown arg (guard short-
    circuits, call_next never runs)."""
    out, reached = await _call({"type": "object", "properties": {"a": {}}}, {"a": 1, "typo": 2})
    assert reached is False  # short-circuited before call_next
    assert getattr(out, "is_error", False) is True
