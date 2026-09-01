"""F2 results: json/text/error/image/audio/bytes + the <=8-byte binary guard (#8)."""

import base64

from mcp.types import AudioContent, ImageContent, TextContent

from ironmcp import Results


def test_json_wraps_a_map_as_pretty_json_success_text():
    r = Results.json({"a": 1})
    assert r.is_error is False
    assert '"a": 1' in r.content[0].text


def test_error_sets_is_error_true():
    r = Results.error("nope")
    assert r.is_error is True
    assert r.content[0].text == "nope"


def test_text_is_plain_success():
    r = Results.text("hello")
    assert r.is_error is False
    assert isinstance(r.content[0], TextContent)
    assert r.content[0].text == "hello"


def test_image_rejects_le_8_bytes_wslg_trap_invariant_8():
    r = Results.image(bytes([1, 2, 3]))
    assert r.is_error is True
    assert "empty or truncated image" in r.content[0].text


def test_image_at_exactly_8_bytes_is_still_rejected():
    r = Results.image(bytes(range(8)))  # length == MIN_BYTES, not > it
    assert r.is_error is True


def test_image_base64_encodes_real_bytes_and_round_trips_exactly():
    data = bytes(range(64))
    r = Results.image(data, mime_type="image/png")
    assert r.is_error is False
    img = r.content[0]
    assert isinstance(img, ImageContent)
    assert img.mime_type == "image/png"
    assert base64.b64decode(img.data) == data


def test_audio_covers_non_png_binary_and_round_trips():
    data = bytes(255 - i for i in range(32))
    r = Results.audio(data, mime_type="audio/wav")
    assert r.is_error is False
    a = r.content[0]
    assert isinstance(a, AudioContent)
    assert a.mime_type == "audio/wav"
    assert base64.b64decode(a.data) == data


def test_audio_also_guards_the_empty_capture():
    assert Results.audio(b"").is_error is True


def test_bytes_helper_guards_le_8_and_routes_by_mime():
    assert Results.bytes(b"1234", mime_type="application/octet-stream").is_error is True
    r = Results.bytes(bytes(range(20)), mime_type="image/jpeg")
    assert r.is_error is False
    assert isinstance(r.content[0], ImageContent)
    r2 = Results.bytes(bytes(range(20)), mime_type="application/octet-stream")
    assert r2.is_error is False
    assert isinstance(r2.content[0], AudioContent)


def test_truncated_text_marks_how_many_chars_were_dropped():
    long = "x" * 100
    t = Results.truncated_text(long, max_chars=10).content[0].text
    assert "[truncated 90 chars]" in t
    assert len(t) < len(long)


def test_truncated_text_leaves_short_text_intact():
    assert Results.truncated_text("hi", max_chars=10).content[0].text == "hi"
