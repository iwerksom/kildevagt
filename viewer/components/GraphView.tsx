"use client";

import type { Entity } from "@/lib/data";
import { toId } from "@/lib/id";

const W = 780;
const H = 680;
const CX = W / 2;
const CY = 305;
const RING = 215;

// Server and browser compute sin/cos differently in the last digits, which breaks hydration. Round.
const round = (n: number) => Math.round(n * 100) / 100;

type Props = {
  title: string;
  entities: Entity[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  countFor: (e: Entity) => number;
};

export const entityId = (e: Entity) => `${e.kind}|${e.key}`;
const short = (text: string, n: number) => (text.length > n ? text.slice(0, n - 1) + "…" : text);

/** Document in the middle, entities in a ring, other documents that mention the same entity outside it. */
export default function GraphView({ title, entities, selected, onSelect, countFor }: Props) {
  const step = (2 * Math.PI) / Math.max(entities.length, 1);
  const placed = entities.map((e, i) => {
    const angle = -Math.PI / 2 + i * step;
    return { e, angle, x: round(CX + RING * Math.cos(angle)), y: round(CY + RING * Math.sin(angle)) };
  });

  // Other documents: one node each, placed outside the ring near the entities that link to them.
  const others = new Map<string, { title: string; source: string; angles: number[]; keys: string[] }>();
  for (const p of placed) {
    for (const o of p.e.alsoIn) {
      const entry = others.get(o.url) ?? { title: o.title, source: o.source, angles: [], keys: [] };
      entry.angles.push(p.angle);
      entry.keys.push(entityId(p.e));
      others.set(o.url, entry);
    }
  }
  const otherNodes = [...others.entries()].map(([url, o], i, all) => ({
    url, ...o, x: round((W / (all.length + 1)) * (i + 1)), y: H - 30,
  }));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Graph of what ${title} mentions`} className="graph">
      <rect width={W} height={H} className="graph-bg" onClick={() => onSelect(null)} />
      {otherNodes.map((o) =>
        o.keys.map((k) => {
          const p = placed.find((q) => entityId(q.e) === k)!;
          return <line key={o.url + k} x1={p.x} y1={p.y} x2={o.x} y2={o.y} className="edge edge-other" />;
        }),
      )}
      {placed.map((p) => {
        const id = entityId(p.e);
        const weak = p.e.mentions.every((m) => m.confidence < 0.9);
        return (
          <line key={id} x1={CX} y1={CY} x2={p.x} y2={p.y}
            className={`edge ${weak ? "edge-weak" : ""} ${selected === id ? "edge-on" : ""}`}
            strokeWidth={Math.min(1 + countFor(p.e) * 0.6, 6)} />
        );
      })}
      {otherNodes.map((o) => (
        <g key={o.url}>
          <a href={`/doc/${toId(o.url)}`}>
            <rect x={o.x - 48} y={o.y - 14} width={96} height={28} rx={6} className="node-other" />
            <text x={o.x} y={o.y - 1} className="label small" textAnchor="middle">{o.source}</text>
            <text x={o.x} y={o.y + 10} className="label tiny" textAnchor="middle">{short(o.title, 16)}</text>
          </a>
        </g>
      ))}
      <g>
        <circle cx={CX} cy={CY} r={58} className="node-doc" />
        <text x={CX} y={CY - 2} textAnchor="middle" className="label doc-label" fontSize={11}>{short(title, 16)}</text>
        <text x={CX} y={CY + 14} textAnchor="middle" className="label tiny">document</text>
      </g>
      {placed.map((p) => {
        const id = entityId(p.e);
        const right = Math.cos(p.angle) >= 0;
        return (
          <g key={id} className={`entity kind-${p.e.kind} ${selected === id ? "on" : ""} ${selected && selected !== id ? "dim" : ""}`}
            onClick={(ev) => { ev.stopPropagation(); onSelect(selected === id ? null : id); }}
            tabIndex={0} role="button" aria-label={`${p.e.kind} ${p.e.name}, ${countFor(p.e)} mentions`}
            onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") onSelect(selected === id ? null : id); }}>
            <circle cx={p.x} cy={p.y} r={9 + Math.min(countFor(p.e), 6)} className="node" />
            <text x={p.x + (right ? 1 : -1) * (16 + Math.min(countFor(p.e), 6))} y={p.y + 4}
              textAnchor={right ? "start" : "end"} className="label">{short(p.e.name, 22)}</text>
          </g>
        );
      })}
    </svg>
  );
}
