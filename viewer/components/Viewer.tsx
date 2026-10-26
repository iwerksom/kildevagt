"use client";

import { useMemo, useState } from "react";
import type { DocumentDetail, Entity } from "@/lib/data";
import { toId } from "@/lib/id";
import GraphView, { entityId } from "./GraphView";

const KINDS: Entity["kind"][] = ["Company", "Organisation", "Person", "Unclassified", "Place"];
const KIND_HELP: Record<Entity["kind"], string> = {
  Company: "a business: legal form (A/S, ApS ...), a known brand, or a business word",
  Organisation: "not a business: association, foundation, waterworks, museum, public-owned company",
  Person: "elected official",
  Unclassified: "spaCy found a name, but nothing says what kind of thing it is",
  Place: "place name, noisy",
};
const MAX_NODES = 24;

function highlight(text: string, name: string) {
  const i = text.toLowerCase().indexOf(name.toLowerCase());
  if (i < 0) return text;
  return (<>{text.slice(0, i)}<mark>{text.slice(i, i + name.length)}</mark>{text.slice(i + name.length)}</>);
}

export default function Viewer({ doc }: { doc: DocumentDetail }) {
  const [kinds, setKinds] = useState<Set<Entity["kind"]>>(new Set(["Company", "Organisation", "Person"]));
  const [item, setItem] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const countFor = (e: Entity) => (item ? e.mentions.filter((m) => m.item === item).length : e.mentions.length);
  const visible = useMemo(
    () => doc.entities.filter((e) => kinds.has(e.kind) && countFor(e) > 0)
      .sort((a, b) => countFor(b) - countFor(a) || a.name.localeCompare(b.name)),
    [doc.entities, kinds, item], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const shown = visible.slice(0, MAX_NODES);
  const chosen = doc.entities.find((e) => entityId(e) === selected) ?? null;
  const mentionsPerItem = (n: string) =>
    doc.entities.filter((e) => kinds.has(e.kind)).reduce((s, e) => s + e.mentions.filter((m) => m.item === n).length, 0);

  const toggleKind = (k: Entity["kind"]) => {
    const next = new Set(kinds);
    next.has(k) ? next.delete(k) : next.add(k);
    setKinds(next);
  };

  return (
    <div className="viewer">
      <section className="pane doc">
        <a href="/" className="back">← all documents</a>
        <h1>{doc.title}</h1>
        <dl className="facts">
          <dt>Source</dt><dd>{doc.source}</dd>
          <dt>Meeting date</dt><dd>{doc.date ?? "unknown"}</dd>
          <dt>Fetched</dt><dd>{doc.fetchedAt.slice(0, 19).replace("T", " ")} UTC</dd>
          <dt>SHA-256</dt><dd><code>{doc.sha256.slice(0, 16)}…</code></dd>
          <dt>Original</dt><dd><a href={doc.url} target="_blank" rel="noreferrer">open the page</a></dd>
        </dl>
        <h2>Agenda items {item && <button className="link" onClick={() => setItem(null)}>show all</button>}</h2>
        <ol className="items">
          {doc.items.map((a) => (
            <li key={a.number}>
              <button className={item === a.number ? "item on" : "item"} onClick={() => setItem(item === a.number ? null : a.number)}>
                <span className="num">{a.number}</span>
                <span className="t">{a.title}</span>
                <span className="badge" title="mentions in this item">{mentionsPerItem(a.number)}</span>
              </button>
            </li>
          ))}
        </ol>
      </section>

      <section className="pane graphpane">
        <div className="toggles" role="group" aria-label="Entity kinds">
          {KINDS.map((k) => (
            <label key={k} className={`toggle kind-${k}`} title={KIND_HELP[k]}>
              <input type="checkbox" checked={kinds.has(k)} onChange={() => toggleKind(k)} />
              <span className="dot" />{k}
            </label>
          ))}
        </div>
        <GraphView title={doc.title} entities={shown} selected={selected} onSelect={setSelected} countFor={countFor} />
        <p className="muted small">
          {shown.length} of {visible.length} entities shown{item ? ` for item ${item}` : ""}. Dashed lines are unclassified names: nothing says what they are.
          Boxes along the bottom are other documents that mention the same name.
        </p>

        <div className="prov" aria-live="polite">
          {chosen ? (
            <>
              <h2>{chosen.name} <span className={`pill kind-${chosen.kind}`}>{chosen.kind}</span>
                {!chosen.verified && chosen.kind !== "Person" && <span className="pill unverified">not verified against CVR</span>}</h2>
              {chosen.alsoIn.length > 0 && (
                <p className="also">Also in: {[...new Map(chosen.alsoIn.map((o) => [o.url, o])).values()].map((o, i) => (
                  <a key={o.url} href={`/doc/${toId(o.url)}`}>{i ? ", " : ""}{o.source} · {o.title}</a>
                ))}</p>
              )}
              <ul className="mentions">
                {chosen.mentions.filter((m) => !item || m.item === item).map((m, i) => (
                  <li key={i}>
                    <div className="meta">item {m.item} · {m.method} · confidence {m.confidence}</div>
                    <blockquote>{highlight(m.snippet, chosen.name)}</blockquote>
                    <div className="meta">
                      fetched {m.fetchedAt.slice(0, 19).replace("T", " ")} · sha256 <code>{m.sha256.slice(0, 12)}</code> ·{" "}
                      <a href={m.sourceUrl} target="_blank" rel="noreferrer">source page</a>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">Click a node to see every sentence it was found in, with the page, time and hash it came from.</p>
          )}
        </div>
      </section>
    </div>
  );
}
