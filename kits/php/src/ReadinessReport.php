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

    /**
     * The wire shape. Ecosystem health-check vocabulary (`status`) + loqu8's
     * map-by-id structure: features/dependencies/data_files are OBJECTS keyed by
     * id/name, so an agent reads `features["<id>"].status` in one hop, there is no
     * list order to keep byte-identical across kits, and duplicate ids cannot hide.
     * `dependencies` (not `libs`) so a server with services rather than native
     * libraries is not misdescribed. The maps are cast to objects so an empty one
     * encodes as `{}` (matching the other kits), never `[]`.
     *
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        $features = [];
        foreach ($this->features as $f) {
            $features[$f->id] = $f->toArray();
        }
        $dependencies = [];
        foreach ($this->libs as $l) {
            $dependencies[$l->name] = $l->toArray();
        }
        $dataFiles = [];
        foreach ($this->dataFiles as $d) {
            $dataFiles[$d->label] = $d->toArray();
        }

        $out = ['app_version' => $this->appVersion];
        if ($this->nativeVersion !== null) {
            $out['native_version'] = $this->nativeVersion;
        }
        $out['status'] = $this->overallStatus()->value;
        $out['features'] = (object) $features;
        $out['dependencies'] = (object) $dependencies;
        $out['data_files'] = (object) $dataFiles;
        $out['platform'] = (object) $this->platform;

        return $out;
    }
}
