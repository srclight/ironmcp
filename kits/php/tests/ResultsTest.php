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
