<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * One feature's readiness. Peer of the Dart `FeatureReadiness` (kits/dart/lib/src/readiness.dart);
 * snake_case JSON, optionals omitted when null/empty.
 */
final class FeatureReadiness
{
    /**
     * @param list<string> $requires
     */
    public function __construct(
        public readonly string $id,
        public readonly string $label,
        public readonly ReadinessStatus $status,
        public readonly array $requires = [],
        public readonly ?string $details = null,
        public readonly ?string $reason = null,
    ) {
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        $out = [
            'id' => $this->id,
            'label' => $this->label,
            'status' => $this->status->value,
        ];
        if ($this->requires !== []) {
            $out['requires'] = $this->requires;
        }
        if ($this->details !== null) {
            $out['details'] = $this->details;
        }
        if ($this->reason !== null) {
            $out['reason'] = $this->reason;
        }

        return $out;
    }
}
