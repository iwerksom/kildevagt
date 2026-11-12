<script lang="ts">
  import type { Entity } from "#lib/types.ts";
  import { toId } from "#lib/id.ts";
  import { entityId } from "#lib/entity.ts";

  const W = 780, H = 680, CX = W / 2, CY = 305, RING = 215;
  const round = (n: number) => Math.round(n * 100) / 100;
  const short = (text: string, n: number) => (text.length > n ? text.slice(0, n - 1) + "…" : text);

  let { title, entities, selected, onselect, countFor }: {
    title: string; entities: Entity[]; selected: string | null;
    onselect: (id: string | null) => void; countFor: (e: Entity) => number;
  } = $props();

  // Document in the middle, entities in a ring, other documents that mention the same entity outside it.
  const placed = $derived.by(() => {
    const step = (2 * Math.PI) / Math.max(entities.length, 1);
    return entities.map((e, i) => {
      const angle = -Math.PI / 2 + i * step;
      return { e, id: entityId(e), angle, x: round(CX + RING * Math.cos(angle)), y: round(CY + RING * Math.sin(angle)) };
    });
  });

  // One node per other document, along the bottom.
  const otherNodes = $derived.by(() => {
    const others = new Map<string, { title: string; source: string; ids: string[] }>();
    for (const p of placed) {
      for (const o of p.e.alsoIn) {
        const entry = others.get(o.url) ?? { title: o.title, source: o.source, ids: [] };
        entry.ids.push(p.id);
        others.set(o.url, entry);
      }
    }
    return [...others.entries()].map(([url, o], i, all) => ({
      url, ...o, x: round((W / (all.length + 1)) * (i + 1)), y: H - 30,
    }));
  });

  const toggle = (id: string) => onselect(selected === id ? null : id);
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label="Graph of what {title} mentions" class="graph">
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <rect width={W} height={H} class="graph-bg" onclick={() => onselect(null)} />

  {#each otherNodes as o (o.url)}
    {#each o.ids as id (id)}
      {@const p = placed.find((q) => q.id === id)!}
      <line x1={p.x} y1={p.y} x2={o.x} y2={o.y} class="edge edge-other" />
    {/each}
  {/each}

  {#each placed as p (p.id)}
    <line x1={CX} y1={CY} x2={p.x} y2={p.y}
      class="edge"
      class:edge-weak={p.e.kind === "Unclassified"}
      class:edge-on={selected === p.id}
      stroke-width={Math.min(1 + countFor(p.e) * 0.6, 6)} />
  {/each}

  {#each otherNodes as o (o.url)}
    <a href="/doc/{toId(o.url)}">
      <rect x={o.x - 48} y={o.y - 14} width={96} height={28} rx={6} class="node-other" />
      <text x={o.x} y={o.y - 1} class="label small" text-anchor="middle">{o.source}</text>
      <text x={o.x} y={o.y + 10} class="label tiny" text-anchor="middle">{short(o.title, 16)}</text>
    </a>
  {/each}

  <circle cx={CX} cy={CY} r={58} class="node-doc" />
  <text x={CX} y={CY - 2} text-anchor="middle" class="label doc-label" font-size={11}>{short(title, 16)}</text>
  <text x={CX} y={CY + 14} text-anchor="middle" class="label tiny">document</text>

  {#each placed as p (p.id)}
    {@const right = Math.cos(p.angle) >= 0}
    {@const n = countFor(p.e)}
    <g class="entity kind-{p.e.kind}" class:on={selected === p.id} class:dim={selected && selected !== p.id}
      role="button" tabindex="0" aria-label="{p.e.kind} {p.e.name}, {n} mentions"
      onclick={(ev) => { ev.stopPropagation(); toggle(p.id); }}
      onkeydown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(p.id); } }}>
      <circle cx={p.x} cy={p.y} r={9 + Math.min(n, 6)} class="node" />
      <text x={p.x + (right ? 1 : -1) * (16 + Math.min(n, 6))} y={p.y + 4}
        text-anchor={right ? "start" : "end"} class="label">{short(p.e.name, 22)}</text>
    </g>
  {/each}
</svg>
