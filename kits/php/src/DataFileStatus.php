<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * A data-file presence check. Peer of the Dart `DataFileStatus`.
 */
final class DataFileStatus
{
    public function __construct(
        public readonly string $label,
        public readonly bool $found,
        public readonly ?string $path = null,
    ) {
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        // label is the map key under `data_files`.
        $out = ['found' => $this->found];
        if ($this->path !== null) {
            $out['path'] = $this->path;
        }

        return $out;
    }
}
