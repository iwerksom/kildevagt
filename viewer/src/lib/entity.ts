import type { Entity } from "./types";

export const entityId = (e: Entity) => `${e.kind}|${e.key}`;
