// The 3-state rule + the advertise stamp. No SDK import; pure. Mirrors the Python kit's
// strict module: the schema is authoritative, and a guard that bricks what it cannot read
// is worse than the bug it prevents.
import { unknownArgsMessage } from "./messages.js";

export type JsonSchema = {
  type?: string;
  properties?: Record<string, unknown>;
  additionalProperties?: boolean;
  [k: string]: unknown;
};

export type ArgCheck =
  | { ok: true }
  | { ok: false; unknown: string[]; accepted: string[]; message: string };

/** True only in state 2: properties present (even {}) and not opted open. */
function isEnforced(schema: JsonSchema | undefined): schema is JsonSchema {
  return (
    !!schema &&
    typeof schema === "object" &&
    schema.properties !== undefined &&
    schema.additionalProperties !== true
  );
}

export function checkUnknownArgs(
  schema: JsonSchema | undefined,
  args: Record<string, unknown> | undefined,
  opts: { reconnectHint?: string; toolName?: string } = {},
): ArgCheck {
  if (!isEnforced(schema)) return { ok: true }; // states 1 (unintrospectable) & 3 (opted open)
  const accepted = Object.keys(schema.properties ?? {});
  const acceptedSet = new Set(accepted);
  const unknown = Object.keys(args ?? {})
    .filter((k) => !acceptedSet.has(k))
    .sort();
  if (unknown.length === 0) return { ok: true };
  return {
    ok: false,
    unknown,
    accepted,
    message: unknownArgsMessage(opts.toolName ?? "tool", unknown, accepted, opts.reconnectHint),
  };
}

export function stampClosed(schema: JsonSchema | undefined): JsonSchema | undefined {
  if (!isEnforced(schema)) return schema;
  return { ...schema, additionalProperties: false };
}
