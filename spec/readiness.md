# ironmcp readiness report

A structured, machine-readable answer to *"is this server actually ready, and if not,
what's wrong?"* — richer than a liveness ping, honest about the difference between a real
failure and an environment that was never going to satisfy a feature.

Every kit (Python, TypeScript, PHP, Dart) emits **this exact shape**, so an agent reads
one server's readiness the same way it reads another's, in any language.

## The shape

```jsonc
{
  "app_version": "2.3.1",
  "native_version": "1.5.0",          // optional; omitted when there is none
  "status": "ready",                   // the overall verdict — see below
  "features": {                        // OBJECT keyed by feature id
    "tts": { "status": "ready", "requires": ["libtts"], "details": "…", "reason": "…" }
    // per-feature value: { status, requires?, details?, reason? } — id is the KEY, not repeated
  },
  "dependencies": {                    // OBJECT keyed by name (native lib, service, db, API…)
    "libtts": { "loaded": true, "symbols_checked": 3, "symbols_ok": 3 }
    // value: { loaded, symbols_checked?, symbols_ok?, error? }
    // symbols_* appear ONLY when an FFI probe ran; a service/db carries just { loaded, error? }
  },
  "data_files": {                      // OBJECT keyed by label
    "dict": { "found": true, "path": "/opt/data/dict.db" }
    // value: { found, path? }
  },
  "platform": { "os": "linux" }        // free-form object
}
```

An empty `features`/`dependencies`/`data_files` is `{}` (an object), never `[]`.

## Why this shape

It is the **ecosystem's health-check vocabulary** — the IETF health-check response draft,
Kubernetes readiness/liveness, and Spring Boot Actuator all key the overall verdict on
**`status`** — combined with a **map-by-id** structure. Keying `features` / `dependencies`
/ `data_files` by id/name means a caller reads `features["<id>"].status` in one hop (no
list scan), there is no array order to keep identical across four languages, and a
duplicate id cannot silently coexist. `dependencies` (not `libs`) so a server whose
dependencies are *services* or *databases* rather than native libraries is not
misdescribed.

## The five states and the verdict

Feature `status` is one of:

| state | meaning | counts toward the verdict? |
|-------|---------|----------------------------|
| `ready` | measured live, working | yes |
| `degraded` | working with reduced capability | yes |
| `failed` | should work, does not | yes |
| `blocked` | the environment cannot satisfy it (e.g. no display) | **no** |
| `off` | intentionally disabled | **no** |

The top-level **`status`** is computed from the features that COUNT (excluding `blocked`
and `off`): `failed` if any counted feature failed, else `degraded` if any is degraded,
else `ready`. So a dev box that can never meet an environmental precondition still reports
`ready` overall — the honest gauge, not a red light for a condition the box was never
going to meet.

## The contract

The field names, the map-by-id structure, the five states, and the exclusion rule are
frozen once published. New optional fields may be added to a per-item value; the keys
above never change meaning. Each kit pins this shape in its own readiness test, and the
four kits are checked to emit the identical structure for the same input.
