"""Feature readiness. ``blocked`` (the environment cannot satisfy it) and ``off``
(intentionally disabled) are EXCLUDED from the overall verdict — a dev box that can never
meet the environment still reports ``ready`` (loqu8 invariant #7).

Ported from ``kits/dart/lib/src/readiness.dart``. ironmcp owns the SHAPE and the verdict
semantics; the app supplies the feature/lib/data checks (no FFI dependency in the kit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

__all__ = [
    "ReadinessStatus",
    "FeatureReadiness",
    "LibraryStatus",
    "DataFileStatus",
    "ReadinessReport",
]


class ReadinessStatus(str, Enum):
    ready = "ready"
    degraded = "degraded"
    failed = "failed"
    blocked = "blocked"
    off = "off"


@dataclass
class FeatureReadiness:
    id: str
    label: str
    status: ReadinessStatus
    requires: list[str] = field(default_factory=list)
    details: Optional[str] = None
    reason: Optional[str] = None

    def to_json(self) -> dict:
        # ``id`` is the map key under ``features``; ``label`` is a display hint kept
        # out of the wire shape so the per-feature value is byte-identical across kits.
        out: dict = {"status": self.status.value}
        if self.requires:
            out["requires"] = list(self.requires)
        if self.details is not None:
            out["details"] = self.details
        if self.reason is not None:
            out["reason"] = self.reason
        return out


@dataclass
class LibraryStatus:
    """A native library check result. ironmcp owns this SHAPE; the actual FFI probe is
    supplied by the app, so the kit carries no ctypes/FFI dependency."""

    name: str
    loaded: bool
    symbols_checked: int = 0
    symbols_ok: int = 0
    error: Optional[str] = None

    def to_json(self) -> dict:
        # ``name`` is the map key under ``dependencies``. The symbol counts are
        # FFI-specific, so they appear ONLY when a probe ran — a non-native
        # dependency (a service, a database) carries just ``loaded`` and an optional
        # ``error``, keeping ``dependencies`` meaningful for every kind of server.
        out: dict = {"loaded": self.loaded}
        if self.symbols_checked > 0:
            out["symbols_checked"] = self.symbols_checked
            out["symbols_ok"] = self.symbols_ok
        if self.error is not None:
            out["error"] = self.error
        return out


@dataclass
class DataFileStatus:
    label: str
    found: bool
    path: Optional[str] = None

    def to_json(self) -> dict:
        # ``label`` is the map key under ``data_files``.
        out: dict = {"found": self.found}
        if self.path is not None:
            out["path"] = self.path
        return out


@dataclass
class ReadinessReport:
    """A full readiness report. ironmcp owns the shape + the verdict semantics; the app
    supplies the feature/lib/data checks."""

    app_version: str
    native_version: Optional[str] = None
    features: list[FeatureReadiness] = field(default_factory=list)
    libs: list[LibraryStatus] = field(default_factory=list)
    data_files: list[DataFileStatus] = field(default_factory=list)
    platform: dict = field(default_factory=dict)

    @property
    def overall_status(self) -> ReadinessStatus:
        """Overall verdict from the features that COUNT — ``blocked``/``off`` are excluded
        (invariant #7). failed > degraded > ready."""
        counted = [
            f
            for f in self.features
            if f.status not in (ReadinessStatus.blocked, ReadinessStatus.off)
        ]
        if any(f.status == ReadinessStatus.failed for f in counted):
            return ReadinessStatus.failed
        if any(f.status == ReadinessStatus.degraded for f in counted):
            return ReadinessStatus.degraded
        return ReadinessStatus.ready

    def to_json(self) -> dict:
        # Ecosystem health-check vocabulary (``status``) + loqu8's map-by-id
        # structure: features/dependencies/data_files are OBJECTS keyed by id/name,
        # so an agent reads ``features["<id>"]["status"]`` in one hop, there is no
        # list order to keep byte-identical across kits, and duplicate ids cannot
        # hide. ``dependencies`` (not ``libs``) so a server with services rather
        # than native libraries is not misdescribed.
        out: dict = {"app_version": self.app_version}
        if self.native_version is not None:
            out["native_version"] = self.native_version
        out["status"] = self.overall_status.value
        out["features"] = {f.id: f.to_json() for f in self.features}
        out["dependencies"] = {l.name: l.to_json() for l in self.libs}
        out["data_files"] = {d.label: d.to_json() for d in self.data_files}
        out["platform"] = self.platform
        return out
