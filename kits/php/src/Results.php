<?php

declare(strict_types=1);

namespace IronMcp;

use Mcp\Schema\Content\AudioContent;
use Mcp\Schema\Content\EmbeddedResource;
use Mcp\Schema\Content\ImageContent;
use Mcp\Schema\Content\TextContent;
use Mcp\Schema\Result\CallToolResult;

/**
 * Content/result helpers — the generic PIPING an app tool rides on. The screenshot/audio CAPTURE
 * stays app-side; ironmcp owns how raw bytes become a well-formed, guarded MCP result. No helper
 * echoes a caller-supplied value.
 *
 * Byte-for-byte peer of the Dart `Results` (kits/dart/lib/src/results.dart): the same minimum-byte
 * floor, the same empty-capture guard, the same truncation marker.
 */
final class Results
{
    /**
     * Minimum bytes that count as real payload. A WSLg/X11 capture can exit 0 yet emit an empty
     * (<=8-byte) file; treat that as a failure, not media (loqu8 invariant #8).
     */
    public const MIN_BYTES = 8;

    /**
     * Success result carrying pretty-printed JSON.
     *
     * @param array<string|int, mixed> $data
     */
    public static function json(array $data): CallToolResult
    {
        $text = json_encode($data, \JSON_PRETTY_PRINT | \JSON_UNESCAPED_SLASHES | \JSON_UNESCAPED_UNICODE);

        return new CallToolResult([new TextContent($text === false ? '{}' : $text)]);
    }

    /** Success result carrying plain text. */
    public static function text(string $message): CallToolResult
    {
        return new CallToolResult([new TextContent($message)]);
    }

    /** An error result (isError: true) so the caller/agent sees the tool failed. */
    public static function error(string $message): CallToolResult
    {
        return new CallToolResult([new TextContent($message)], isError: true);
    }

    /**
     * Image result, or an {@see error} when the bytes are missing/too small (invariant #8).
     *
     * @param string $bytes raw (NOT yet base64-encoded) image bytes
     */
    public static function image(string $bytes, string $mimeType = 'image/png'): CallToolResult
    {
        $guard = self::guardBytes($bytes, 'image');
        if ($guard !== null) {
            return $guard;
        }

        return new CallToolResult([new ImageContent(base64_encode($bytes), $mimeType)]);
    }

    /**
     * Audio result (iCE speaks), or an {@see error} when empty/too small. Proves the piping is not
     * PNG-only.
     *
     * @param string $bytes raw (NOT yet base64-encoded) audio bytes
     */
    public static function audio(string $bytes, string $mimeType = 'audio/wav'): CallToolResult
    {
        $guard = self::guardBytes($bytes, 'audio');
        if ($guard !== null) {
            return $guard;
        }

        return new CallToolResult([new AudioContent(base64_encode($bytes), $mimeType)]);
    }

    /**
     * Generic binary result carried as an embedded blob resource, or an {@see error} when empty/too
     * small (invariant #8). The non-image, non-audio piping path.
     *
     * @param string $bytes raw (NOT yet base64-encoded) binary bytes
     */
    public static function bytes(
        string $bytes,
        string $mimeType = 'application/octet-stream',
        string $uri = 'ironmcp://bytes',
    ): CallToolResult {
        $guard = self::guardBytes($bytes, 'binary');
        if ($guard !== null) {
            return $guard;
        }

        return new CallToolResult([EmbeddedResource::fromBlob($uri, base64_encode($bytes), $mimeType)]);
    }

    /**
     * Truncate $body to $maxChars, appending a marker naming how many chars were dropped, so an
     * agent never mistakes a partial payload for the whole thing.
     */
    public static function truncatedText(string $body, int $maxChars = 20000): CallToolResult
    {
        $len = mb_strlen($body, 'UTF-8');
        if ($len <= $maxChars) {
            return self::text($body);
        }
        $dropped = $len - $maxChars;

        return self::text(mb_substr($body, 0, $maxChars, 'UTF-8') . "\n…[truncated {$dropped} chars]");
    }

    /** The empty-capture guard: an {@see error} when <=MIN_BYTES, else null (caller proceeds). */
    private static function guardBytes(string $bytes, string $kind): ?CallToolResult
    {
        $n = \strlen($bytes);
        if ($n <= self::MIN_BYTES) {
            return self::error(
                "empty or truncated {$kind} ({$n} bytes) — the capture produced no usable data",
            );
        }

        return null;
    }
}
