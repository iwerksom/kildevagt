import neo4j, { Driver, isInt } from "neo4j-driver";

// One driver per server process. The password comes from .env.local (see .env.local.example).
const globalForNeo4j = globalThis as unknown as { driver?: Driver };

export function driver(): Driver {
  if (!globalForNeo4j.driver) {
    const password = process.env.NEO4J_PASSWORD;
    if (!password) throw new Error("NEO4J_PASSWORD is not set. Copy .env.local.example to .env.local.");
    globalForNeo4j.driver = neo4j.driver("bolt://127.0.0.1:7687", neo4j.auth.basic("neo4j", password));
  }
  return globalForNeo4j.driver;
}

/** Neo4j integers are objects; turn them into plain numbers. */
export function plain<T>(value: T): T {
  if (isInt(value)) return (value as unknown as { toNumber(): number }).toNumber() as unknown as T;
  if (Array.isArray(value)) return value.map(plain) as unknown as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, plain(v)])) as T;
  }
  return value;
}

export async function run<T = Record<string, unknown>>(cypher: string, params: Record<string, unknown> = {}): Promise<T[]> {
  const session = driver().session({ defaultAccessMode: neo4j.session.READ });
  try {
    const result = await session.run(cypher, params);
    return result.records.map((r) => plain(r.toObject()) as T);
  } finally {
    await session.close();
  }
}
