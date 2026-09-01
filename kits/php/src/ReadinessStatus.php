<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * Feature readiness status. `blocked` (the environment cannot satisfy it) and `off` (intentionally
 * disabled) are EXCLUDED from the overall verdict — a dev box that can never meet the environment
 * still reports `ready` (loqu8 invariant #7).
 */
enum ReadinessStatus: string
{
    case Ready = 'ready';
    case Degraded = 'degraded';
    case Failed = 'failed';
    case Blocked = 'blocked';
    case Off = 'off';
}
