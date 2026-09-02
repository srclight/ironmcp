<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * A native library check result. ironmcp owns this SHAPE; the actual probe (dlopen + symbol lookup)
 * is supplied by the app, so the kit carries no FFI dependency. Peer of the Dart `LibraryStatus`.
 */
final class LibraryStatus
{
    public function __construct(
        public readonly string $name,
        public readonly bool $loaded,
        public readonly int $symbolsChecked = 0,
        public readonly int $symbolsOk = 0,
        public readonly ?string $error = null,
    ) {
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        // name is the map key under `dependencies`. Symbol counts are FFI-specific,
        // so they appear ONLY when a probe ran — a service/database dependency
        // carries just `loaded` and an optional `error`.
        $out = ['loaded' => $this->loaded];
        if ($this->symbolsChecked > 0) {
            $out['symbols_checked'] = $this->symbolsChecked;
            $out['symbols_ok'] = $this->symbolsOk;
        }
        if ($this->error !== null) {
            $out['error'] = $this->error;
        }

        return $out;
    }
}
