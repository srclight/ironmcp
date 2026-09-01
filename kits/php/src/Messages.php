<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * The unknown-argument refusal message. No SDK import; pure. Byte-compatible in intent with the
 * Python and TypeScript kits: name the keys, never echo values, cap the enumeration, diagnose an
 * NFKC-confusable key by codepoint (when ext-intl is present), and end with a reconnect hint.
 */
final class Messages
{
    public const DEFAULT_RECONNECT_HINT = "check the server's reported revision and reconnect the MCP";

    /** The error message's SIZE is bounded by the server, never by its input. Only key NAMES are
     *  ever echoed, and only the first _MAX_ENUMERATED of them. */
    public const MAX_ENUMERATED = 10;

    /**
     * @param list<string> $unknown
     * @param list<string> $accepted
     */
    public static function unknownArgs(
        string $name,
        array $unknown,
        array $accepted,
        string $reconnectHint = self::DEFAULT_RECONNECT_HINT,
    ): string {
        $shown = array_slice($unknown, 0, self::MAX_ENUMERATED);
        $more = count($unknown) - count($shown);
        $listed = implode(', ', $shown) . ($more > 0 ? ", and {$more} more" : '');

        $sortedAccepted = $accepted;
        sort($sortedAccepted);
        $accepts = $sortedAccepted ? implode(', ', $sortedAccepted) : '(no arguments)';

        $parts = [
            "unknown argument(s): {$listed}.",
            "Tool '{$name}' accepts: {$accepts}.",
            'Nothing was executed and no result was computed.',
        ];

        $hints = self::confusableHints($shown, $accepted);
        if ($hints) {
            $parts[] = 'Note: ' . implode('; ', $hints) . '.';
        }

        $parts[] = 'If you expected these arguments to work, this server process is probably running '
            . "older code than you think - {$reconnectHint}.";

        return implode(' ', $parts);
    }

    /**
     * NFKC confusables: a key written with U+FF41 is glyph-identical to an accepted 'a'. THE SCHEMA
     * IS AUTHORITATIVE FOR NAMES, so it is still refused, but the codepoint is named. Requires
     * ext-intl; without it the diagnosis is silently skipped (the refusal still stands).
     *
     * @param list<string> $shown
     * @param list<string> $accepted
     * @return list<string>
     */
    private static function confusableHints(array $shown, array $accepted): array
    {
        if (!class_exists('Normalizer')) {
            return [];
        }
        $normAccepted = [];
        foreach ($accepted as $a) {
            $normAccepted[\Normalizer::normalize($a, \Normalizer::FORM_KC)] = $a;
        }
        $hints = [];
        foreach ($shown as $k) {
            $canon = \Normalizer::normalize($k, \Normalizer::FORM_KC);
            if ($canon !== $k && isset($normAccepted[$canon])) {
                $cps = implode(' ', array_map(
                    static fn (string $c): string => 'U+' . strtoupper(sprintf('%04X', mb_ord($c, 'UTF-8'))),
                    mb_str_split($k, 1, 'UTF-8'),
                ));
                $hints[] = "'{$k}' ({$cps}) normalises to '{$normAccepted[$canon]}', which IS accepted";
            }
        }
        return $hints;
    }
}
