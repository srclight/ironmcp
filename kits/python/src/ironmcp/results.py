"""Content/result helpers — the generic PIPING an app tool rides on.

The screenshot/audio CAPTURE stays app-side; ironmcp owns how raw bytes become a
well-formed, guarded MCP result. No helper echoes a caller-supplied value.

A WSLg/X11 capture can exit 0 yet emit an empty (``<=8``-byte) file; every binary
helper treats that as a FAILURE, not media (loqu8 invariant #8). Ported from the Dart
kit's ``Results`` (``kits/dart/lib/src/results.dart``) — same contract, Python idiom.
"""

from __future__ import annotations

import base64
import json as _json

from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent

__all__ = ["Results", "MIN_BYTES"]

# Minimum bytes that count as real payload (loqu8 invariant #8).
MIN_BYTES = 8


class Results:
    """Static builders for well-formed :class:`CallToolResult` values."""

    def __init__(self) -> None:  # pragma: no cover - not meant to be instantiated
        raise TypeError("Results is a namespace of static helpers, not a type")

    @staticmethod
    def json(data: dict) -> CallToolResult:
        """Success result carrying pretty-printed JSON."""
        return CallToolResult(
            content=[TextContent(type="text", text=_json.dumps(data, indent=2))]
        )

    @staticmethod
    def text(message: str) -> CallToolResult:
        """Success result carrying plain text."""
        return CallToolResult(content=[TextContent(type="text", text=message)])

    @staticmethod
    def error(message: str) -> CallToolResult:
        """An error result (``is_error=True``) so the caller/agent sees the tool failed."""
        return CallToolResult(
            content=[TextContent(type="text", text=message)], is_error=True
        )

    @staticmethod
    def image(data: bytes, *, mime_type: str = "image/png") -> CallToolResult:
        """Image result, or an :meth:`error` when the bytes are missing/too small."""
        return Results._binary(data, mime_type, kind="image")

    @staticmethod
    def audio(data: bytes, *, mime_type: str = "audio/wav") -> CallToolResult:
        """Audio result (iCE speaks), or an :meth:`error` when empty/too small.

        Proves the piping is not PNG-only.
        """
        return Results._binary(data, mime_type, kind="audio")

    @staticmethod
    def bytes(data: bytes, *, mime_type: str, kind: str = "binary") -> CallToolResult:
        """Generic binary result carried as a base64 blob, guarded by :data:`MIN_BYTES`.

        Emitted as an :class:`ImageContent` when the mime is ``image/*``, otherwise as an
        :class:`AudioContent` (the two binary content shapes MCP v2 offers). The
        ``<=8``-byte guard is identical to :meth:`image` / :meth:`audio`.
        """
        return Results._binary(data, mime_type, kind=kind)

    @staticmethod
    def _binary(data: bytes, mime_type: str, *, kind: str) -> CallToolResult:
        if len(data) <= MIN_BYTES:
            return Results.error(
                f"empty or truncated {kind} ({len(data)} bytes) — "
                "the capture produced no usable data"
            )
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        # image/* rides ImageContent; everything else rides AudioContent (the two
        # binary content kinds MCP v2 defines). A caller who wants audio calls audio().
        if kind == "image" or mime_type.startswith("image/"):
            block = ImageContent(type="image", data=encoded, mime_type=mime_type)
        else:
            block = AudioContent(type="audio", data=encoded, mime_type=mime_type)
        return CallToolResult(content=[block])

    @staticmethod
    def truncated_text(body: str, *, max_chars: int = 20000) -> CallToolResult:
        """Truncate ``body`` to ``max_chars``, marking how many chars were dropped so an
        agent never mistakes a partial payload for the whole thing."""
        if len(body) <= max_chars:
            return Results.text(body)
        dropped = len(body) - max_chars
        return Results.text(f"{body[:max_chars]}\n…[truncated {dropped} chars]")
