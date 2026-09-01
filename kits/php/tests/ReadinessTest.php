<?php

declare(strict_types=1);

namespace IronMcp\Tests;

use IronMcp\DataFileStatus;
use IronMcp\FeatureReadiness;
use IronMcp\LibraryStatus;
use IronMcp\ReadinessReport;
use IronMcp\ReadinessStatus;
use PHPUnit\Framework\TestCase;

final class ReadinessTest extends TestCase
{
    /** @param list<FeatureReadiness> $f */
    private static function report(array $f): ReadinessReport
    {
        return new ReadinessReport(appVersion: '1', features: $f);
    }

    /** Invariant #7: the overall verdict EXCLUDES blocked and off. */
    public function testOverallExcludesBlockedAndOff(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Ready),
            new FeatureReadiness('b', 'B', ReadinessStatus::Blocked),
            new FeatureReadiness('c', 'C', ReadinessStatus::Off),
        ]);
        $this->assertSame(ReadinessStatus::Ready, $r->overallStatus());
    }

    /** The dev-box case: all blocked/off still yields ready, never failed. */
    public function testAllBlockedOrOffStillYieldsReady(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Blocked),
            new FeatureReadiness('b', 'B', ReadinessStatus::Off),
        ]);
        $this->assertSame(ReadinessStatus::Ready, $r->overallStatus());
    }

    public function testAFailedCountedFeatureMakesOverallFailed(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Ready),
            new FeatureReadiness('b', 'B', ReadinessStatus::Failed),
        ]);
        $this->assertSame(ReadinessStatus::Failed, $r->overallStatus());
    }

    public function testADegradedFeatureMakesOverallDegraded(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Degraded),
        ]);
        $this->assertSame(ReadinessStatus::Degraded, $r->overallStatus());
    }

    /**
     * Gap #9: failed BEATS degraded when BOTH are counted at once. The two-loop ordering in
     * overallStatus() must return Failed even though a Degraded feature is also present (and, here,
     * appears BEFORE the failed one in the list) — proving the precedence is by status, not by order.
     */
    public function testFailedBeatsDegradedWhenBothArePresent(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Degraded),
            new FeatureReadiness('b', 'B', ReadinessStatus::Failed),
            new FeatureReadiness('c', 'C', ReadinessStatus::Degraded),
        ]);
        $this->assertSame(ReadinessStatus::Failed, $r->overallStatus());
    }

    /** A failed feature that is itself blocked/off must NOT count (guards the exclusion). */
    public function testABlockedFailedLikeStatusDoesNotDragTheVerdict(): void
    {
        $r = self::report([
            new FeatureReadiness('a', 'A', ReadinessStatus::Ready),
            new FeatureReadiness('b', 'B', ReadinessStatus::Blocked),
        ]);
        $this->assertSame(ReadinessStatus::Ready, $r->overallStatus());
    }

    public function testToArrayIsStableSnakeCaseWithTheComputedVerdict(): void
    {
        $j = (new ReadinessReport(
            appVersion: '2.0',
            nativeVersion: '1.5',
            features: [new FeatureReadiness('a', 'A', ReadinessStatus::Ready, requires: ['x'])],
            libs: [new LibraryStatus('libfoo', true, 3, 3)],
            dataFiles: [new DataFileStatus('dict', true, '/x')],
            platform: ['os' => 'linux'],
        ))->toArray();

        $this->assertSame('2.0', $j['app_version']);
        $this->assertSame('ready', $j['overall_status']);
        $this->assertSame(3, $j['libs'][0]['symbols_ok']);
        $this->assertSame(['x'], $j['features'][0]['requires']);
        $this->assertTrue($j['data_files'][0]['found']);
    }
}
