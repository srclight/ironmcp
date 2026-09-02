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
        // id is the map key under `features`; label is a display hint kept out of
        // the wire shape so the per-feature value is byte-identical across kits.
        $out = ['status' => $this->status->value];
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
