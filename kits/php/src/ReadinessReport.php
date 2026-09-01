<?php

declare(strict_types=1);

namespace IronMcp;

/**
 * A full readiness report. ironmcp owns the shape + the verdict semantics; the app supplies the
 * feature/lib/data checks. Peer of the Dart `ReadinessReport` (kits/dart/lib/src/readiness.dart).
 */
final class ReadinessReport
{
    /**
     * @param list<FeatureReadiness> $features
     * @param list<LibraryStatus>    $libs
     * @param list<DataFileStatus>   $dataFiles
     * @param array<string, mixed>   $platform
     */
    public function __construct(
        public readonly string $appVersion,
        public readonly ?string $nativeVersion = null,
        public readonly array $features = [],
        public readonly array $libs = [],
        public readonly array $dataFiles = [],
        public readonly array $platform = [],
    ) {
    }

    /**
     * Overall verdict from the features that COUNT — `blocked`/`off` are excluded (invariant #7).
     * failed > degraded > ready.
     */
    public function overallStatus(): ReadinessStatus
    {
        $counted = array_filter(
            $this->features,
            static fn (FeatureReadiness $f): bool => $f->status !== ReadinessStatus::Blocked
                && $f->status !== ReadinessStatus::Off,
        );
        foreach ($counted as $f) {
            if ($f->status === ReadinessStatus::Failed) {
                return ReadinessStatus::Failed;
            }
        }
        foreach ($counted as $f) {
            if ($f->status === ReadinessStatus::Degraded) {
                return ReadinessStatus::Degraded;
            }
        }

        return ReadinessStatus::Ready;
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        $out = ['app_version' => $this->appVersion];
        if ($this->nativeVersion !== null) {
            $out['native_version'] = $this->nativeVersion;
        }
        $out['overall_status'] = $this->overallStatus()->value;
        $out['features'] = array_map(static fn (FeatureReadiness $f): array => $f->toArray(), $this->features);
        $out['libs'] = array_map(static fn (LibraryStatus $l): array => $l->toArray(), $this->libs);
        $out['data_files'] = array_map(static fn (DataFileStatus $d): array => $d->toArray(), $this->dataFiles);
        $out['platform'] = (object) $this->platform;

        return $out;
    }
}
