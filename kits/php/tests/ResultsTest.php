<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\Results;
use Mcp\Schema\Content\AudioContent;
use Mcp\Schema\Content\EmbeddedResource;
use Mcp\Schema\Content\ImageContent;
use Mcp\Schema\Content\TextContent;
use PHPUnit\Framework\TestCase;

final class ResultsTest extends TestCase
{
    public function testJsonWrapsAMapAsPrettyJsonSuccessText(): void
    {
        $r = Results::json(['a' => 1]);
        $this->assertFalse($r->isError);
        $this->assertInstanceOf(TextContent::class, $r->content[0]);
        $this->assertStringContainsString('"a": 1', $r->content[0]->text);
    }

    public function testErrorSetsIsErrorTrue(): void
    {
        $r = Results::error('nope');
        $this->assertTrue($r->isError);
        $this->assertSame('nope', $r->content[0]->text);
    }

    /** Invariant #8: the WSLg empty-capture trap — <=8 bytes is a failure, not media. */
    public function testImageRejectsEightBytesOrFewer(): void
    {
        $r = Results::image("\x01\x02\x03");
        $this->assertTrue($r->isError);
        $this->assertStringContainsString('empty or truncated image', $r->content[0]->text);

        // Exactly 8 bytes is still rejected (the boundary is <=8).
        $this->assertTrue(Results::image(str_repeat('x', 8))->isError);
    }

    /**
     * Canonical fix #6: the EXACT byte boundary is pinned in both directions. 8 bytes is the largest
     * rejected size; 9 bytes — the smallest real payload — is accepted as media. An off-by-one on
     * the `<= MIN_BYTES` guard (e.g. `<`) would slip an empty capture through, or reject a minimal one.
     */
    public function testByteGuardBoundaryIsExactlyEightRejectNineAccept(): void
    {
        // 8 bytes: rejected across every media path.
        $this->assertTrue(Results::image(str_repeat('x', 8))->isError, '8 bytes must be rejected');
        $this->assertTrue(Results::audio(str_repeat('x', 8))->isError, '8 bytes must be rejected');
        $this->assertTrue(Results::bytes(str_repeat('x', 8))->isError, '8 bytes must be rejected');

        // 9 bytes: accepted as real media across every path.
        $nine = str_repeat('x', 9);
        $this->assertFalse(Results::image($nine)->isError, '9 bytes is the smallest accepted payload');
        $this->assertFalse(Results::audio($nine)->isError, '9 bytes is the smallest accepted payload');
        $this->assertFalse(Results::bytes($nine)->isError, '9 bytes is the smallest accepted payload');
        // And it round-trips intact.
        $this->assertSame($nine, base64_decode(Results::image($nine)->content[0]->data, true));
    }

    /**
     * Gap #11: json() falls back to '{}' when json_encode fails (malformed UTF-8, NAN, recursion).
     * A raw invalid UTF-8 byte sequence makes json_encode return false; the result must still be a
     * well-formed success TextContent carrying '{}', never a crash or a `false` cast to ''.
     */
    public function testJsonFallsBackToEmptyObjectOnEncodeFailure(): void
    {
        $r = Results::json(['bad' => "\xB1\x31"]); // invalid UTF-8 -> json_encode returns false
        $this->assertFalse($r->isError);
        $this->assertInstanceOf(TextContent::class, $r->content[0]);
        $this->assertSame('{}', $r->content[0]->text);
    }

    /**
     * Gap #12: truncatedText counts CHARACTERS not bytes, and must not split a multibyte codepoint
     * at the boundary. With 30 multibyte chars (each 3 bytes in UTF-8) truncated to 10 chars, the
     * kept prefix is exactly the first 10 chars, the marker reports 20 dropped, and the whole result
     * is still valid UTF-8 (no half-codepoint at the cut).
     */
    public function testTruncatedTextIsMultibyteSafe(): void
    {
        $body = str_repeat('中', 30); // 30 chars, 90 bytes
        $t = Results::truncatedText($body, 10)->content[0]->text;

        $this->assertStringStartsWith(str_repeat('中', 10), $t, 'the first 10 CHARS are kept intact');
        $this->assertStringContainsString('[truncated 20 chars]', $t, 'dropped count is by char, not byte');
        $this->assertSame($t, mb_convert_encoding($t, 'UTF-8', 'UTF-8'), 'no codepoint split at the boundary');
        // The kept payload is exactly 10 multibyte chars, never 10 bytes.
        $prefix = mb_substr($t, 0, 10, 'UTF-8');
        $this->assertSame(str_repeat('中', 10), $prefix);
    }

    public function testImageBase64EncodesRealBytesByteSafely(): void
    {
        $bytes = '';
        for ($i = 0; $i < 64; ++$i) {
            $bytes .= \chr($i);
        }
        $r = Results::image($bytes, 'image/png');
        $this->assertFalse($r->isError);
        $img = $r->content[0];
        $this->assertInstanceOf(ImageContent::class, $img);
        $this->assertSame('image/png', $img->mimeType);
        $this->assertSame($bytes, base64_decode($img->data, true));
    }

    public function testAudioCoversNonPngBinaryAndRoundTrips(): void
    {
        $bytes = '';
        for ($i = 0; $i < 32; ++$i) {
            $bytes .= \chr(255 - $i);
        }
        $r = Results::audio($bytes, 'audio/wav');
        $this->assertFalse($r->isError);
        $a = $r->content[0];
        $this->assertInstanceOf(AudioContent::class, $a);
        $this->assertSame('audio/wav', $a->mimeType);
        $this->assertSame($bytes, base64_decode($a->data, true));
    }

    public function testAudioAlsoGuardsTheEmptyCapture(): void
    {
        $this->assertTrue(Results::audio('')->isError);
    }

    /** Invariant #8 for the generic binary path: bytes rejects <=8 bytes, else an embedded blob. */
    public function testBytesRejectsTinyPayloadAndCarriesRealBlob(): void
    {
        $this->assertTrue(Results::bytes('tiny')->isError);

        $payload = random_bytes(40);
        $r = Results::bytes($payload, 'application/octet-stream');
        $this->assertFalse($r->isError);
        $res = $r->content[0];
        $this->assertInstanceOf(EmbeddedResource::class, $res);
        $this->assertSame($payload, base64_decode($res->resource->blob, true));
    }

    public function testTruncatedTextMarksHowManyCharsWereDropped(): void
    {
        $long = str_repeat('x', 100);
        $t = Results::truncatedText($long, 10)->content[0]->text;
        $this->assertStringContainsString('[truncated 90 chars]', $t);
        $this->assertLessThan(\strlen($long), mb_strlen($t));
    }

    public function testTruncatedTextLeavesShortTextIntact(): void
    {
        $this->assertSame('hi', Results::truncatedText('hi', 10)->content[0]->text);
    }
}
