<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * The retryable bind failure: the port is momentarily unavailable (Windows TIME_WAIT / EADDRINUSE
 * while a prior process still holds it). A [bind] callable throws this to ask {@see Daemon::start}
 * to retry; every OTHER throwable fast-fails with no retry. This is the PHP stand-in for Dart's
 * `SocketException` discriminator (kits/dart/lib/src/serve.dart).
 */
final class BindBusyException extends \RuntimeException
{
}
