<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * The 3-state rule + the advertise stamp. No SDK import; pure. The schema is authoritative, and a
 * guard that bricks what it cannot read is worse than the bug it prevents.
 */
final class StrictArgs
{
    /**
     * @param array<string, mixed>|null $schema a JSON Schema object as a PHP array
     * @param array<string, mixed>|null $args
     * @return array{ok: true}|array{ok: false, unknown: list<string>, accepted: list<string>, message: string}
     */
    public static function check(?array $schema, ?array $args, string $toolName = 'tool', string $reconnectHint = Messages::DEFAULT_RECONNECT_HINT): array
    {
        if (!self::isEnforced($schema)) {
            return ['ok' => true]; // states 1 (unintrospectable) & 3 (opted open)
        }
        $accepted = array_keys($schema['properties'] ?? []);
        $acceptedSet = array_fill_keys($accepted, true);
        $unknown = array_values(array_filter(
            array_keys($args ?? []),
            static fn ($k) => !isset($acceptedSet[$k]),
        ));
        sort($unknown);
        if ($unknown === []) {
            return ['ok' => true];
        }

        return [
            'ok' => false,
            'unknown' => $unknown,
            'accepted' => $accepted,
            'message' => Messages::unknownArgs($toolName, $unknown, $accepted, $reconnectHint),
        ];
    }

    /**
     * @param array<string, mixed>|null $schema
     * @return array<string, mixed>|null
     */
    public static function stampClosed(?array $schema): ?array
    {
        if (!self::isEnforced($schema)) {
            return $schema;
        }
        $schema['additionalProperties'] = false;

        return $schema;
    }

    /** True only in state 2: properties present (even []) and not opted open. */
    private static function isEnforced(?array $schema): bool
    {
        return $schema !== null
            && array_key_exists('properties', $schema)
            && (($schema['additionalProperties'] ?? null) !== true);
    }
}
