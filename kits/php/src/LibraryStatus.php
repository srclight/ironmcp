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
        $out = [
            'name' => $this->name,
            'loaded' => $this->loaded,
            'symbols_checked' => $this->symbolsChecked,
            'symbols_ok' => $this->symbolsOk,
        ];
        if ($this->error !== null) {
            $out['error'] = $this->error;
        }

        return $out;
    }
}
