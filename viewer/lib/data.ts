import { run } from "./neo4j";

export type DocumentRow = {
  url: string; title: string; source: string; date: string | null;
  change: string; fetchedAt: string; items: number; mentions: number;
};

export type Mention = {
  item: string; snippet: string; method: string; confidence: number;
  sourceUrl: string; fetchedAt: string; sha256: string;
};

export type Entity = {
  key: string; kind: "Company" | "Organisation" | "Person" | "Place"; name: string;
  verified: boolean; mentions: Mention[]; alsoIn: { title: string; source: string; url: string }[];
};

export type DocumentDetail = {
  url: string; title: string; source: string; date: string | null; sha256: string; fetchedAt: string;
  items: { number: string; title: string }[]; entities: Entity[];
};

export { toId, fromId } from "./id";

export function listDocuments(): Promise<DocumentRow[]> {
  return run<DocumentRow>(`
    MATCH (d:Document)<-[:RECORDED_IN]-(m:Meeting)
    OPTIONAL MATCH (a:AgendaItem)-[:PART_OF]->(m)
    WITH d, m, count(a) AS items
    OPTIONAL MATCH (d)-[r:MENTIONS]->()
    RETURN d.url AS url, d.title AS title, d.source_id AS source, m.date AS date,
           d.last_change AS change, d.fetched_at AS fetchedAt, items, count(r) AS mentions
    ORDER BY date DESC, source`);
}

export async function getDocument(url: string): Promise<DocumentDetail | null> {
  const [doc] = await run<Omit<DocumentDetail, "items" | "entities">>(`
    MATCH (d:Document {url: $url})<-[:RECORDED_IN]-(m:Meeting)
    RETURN d.url AS url, d.title AS title, d.source_id AS source, m.date AS date,
           d.sha256 AS sha256, d.fetched_at AS fetchedAt`, { url });
  if (!doc) return null;

  const items = await run<{ number: string; title: string }>(`
    MATCH (a:AgendaItem)-[:PART_OF]->(:Meeting {url: $url})
    RETURN a.number AS number, a.title AS title
    ORDER BY toInteger(a.number), a.number`, { url });

  const rows = await run<{ kind: Entity["kind"]; key: string; name: string; verified: boolean | null; r: Record<string, unknown> }>(`
    MATCH (:Document {url: $url})-[r:MENTIONS]->(e)
    RETURN labels(e)[0] AS kind, e.key AS key, e.name AS name, e.verified AS verified, properties(r) AS r`, { url });

  const others = await run<{ key: string; title: string; source: string; url: string }>(`
    MATCH (:Document {url: $url})-[:MENTIONS]->(e)<-[:MENTIONS]-(o:Document)
    WHERE o.url <> $url
    RETURN DISTINCT e.key AS key, o.title AS title, o.source_id AS source, o.url AS url`, { url });

  const byKey = new Map<string, Entity>();
  for (const row of rows) {
    const id = `${row.kind}|${row.key}`;
    const entity = byKey.get(id) ?? { key: row.key, kind: row.kind, name: row.name, verified: !!row.verified, mentions: [], alsoIn: [] };
    entity.mentions.push({
      item: String(row.r.item ?? ""), snippet: String(row.r.snippet ?? ""), method: String(row.r.method ?? ""),
      confidence: Number(row.r.confidence ?? 0), sourceUrl: String(row.r.source_url ?? ""),
      fetchedAt: String(row.r.fetched_at ?? ""), sha256: String(row.r.sha256 ?? ""),
    });
    byKey.set(id, entity);
  }
  for (const o of others) {
    for (const e of byKey.values()) if (e.key === o.key) e.alsoIn.push({ title: o.title, source: o.source, url: o.url });
  }
  return { ...doc, items, entities: [...byKey.values()] };
}
