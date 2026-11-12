<script lang="ts">
  import type { DocumentDetail, Entity } from "#lib/types.ts";
  import { toId } from "#lib/id.ts";
  import { entityId } from "#lib/entity.ts";
  import GraphView from "./GraphView.svelte";

  const KINDS: Entity["kind"][] = ["Company", "Organisation", "Person", "Unclassified", "Place"];
  const KIND_HELP: Record<Entity["kind"], string> = {
    Company: "a business: legal form (A/S, ApS ...), a known brand, or a business word",
    Organisation: "not a business: association, foundation, waterworks, museum, public-owned company",
    Person: "elected official",
    Unclassified: "spaCy found a name, but nothing says what kind of thing it is",
    Place: "place name, noisy",
  };
  const MAX_NODES = 24;

  let { doc }: { doc: DocumentDetail } = $props();

  let kinds = $state(new Set<Entity["kind"]>(["Company", "Organisation", "Person"]));
  let item = $state<string | null>(null);
  let selected = $state<string | null>(null);

  const countFor = (e: Entity) => (item ? e.mentions.filter((m) => m.item === item).length : e.mentions.length);
  const visible = $derived(
    doc.entities.filter((e) => kinds.has(e.kind) && countFor(e) > 0)
      .sort((a, b) => countFor(b) - countFor(a) || a.name.localeCompare(b.name)),
  );
  const shown = $derived(visible.slice(0, MAX_NODES));
  const chosen = $derived(doc.entities.find((e) => entityId(e) === selected) ?? null);
  const mentionsPerItem = (n: string) =>
    doc.entities.filter((e) => kinds.has(e.kind)).reduce((s, e) => s + e.mentions.filter((m) => m.item === n).length, 0);

  function toggleKind(k: Entity["kind"]) {
    const next = new Set(kinds);
    if (next.has(k)) next.delete(k); else next.add(k);
    kinds = next;
  }

  const stamp = (iso: string) => iso.slice(0, 19).replace("T", " ");

  function split(text: string, name: string): [string, string, string] {
    const i = text.toLowerCase().indexOf(name.toLowerCase());
    return i < 0 ? [text, "", ""] : [text.slice(0, i), text.slice(i, i + name.length), text.slice(i + name.length)];
  }

  const alsoIn = $derived(chosen ? [...new Map(chosen.alsoIn.map((o) => [o.url, o])).values()] : []);
</script>

<div class="viewer">
  <section class="pane doc">
    <a href="/" class="back">← all documents</a>
    <h1>{doc.title}</h1>
    <dl class="facts">
      <dt>Source</dt><dd>{doc.source}</dd>
      <dt>Meeting date</dt><dd>{doc.date ?? "unknown"}</dd>
      <dt>Fetched</dt><dd>{stamp(doc.fetchedAt)} UTC</dd>
      <dt>SHA-256</dt><dd><code>{doc.sha256.slice(0, 16)}…</code></dd>
      <dt>Original</dt><dd><a href={doc.url} target="_blank" rel="noreferrer">open the page</a></dd>
    </dl>
    <h2>Agenda items {#if item}<button class="link" onclick={() => (item = null)}>show all</button>{/if}</h2>
    <ol class="items">
      {#each doc.items as a (a.number)}
        <li>
          <button class={item === a.number ? "item on" : "item"} onclick={() => (item = item === a.number ? null : a.number)}>
            <span class="num">{a.number}</span>
            <span class="t">{a.title}</span>
            <span class="badge" title="mentions in this item">{mentionsPerItem(a.number)}</span>
          </button>
        </li>
      {/each}
    </ol>
  </section>

  <section class="pane graphpane">
    <div class="toggles" role="group" aria-label="Entity kinds">
      {#each KINDS as k (k)}
        <label class="toggle kind-{k}" title={KIND_HELP[k]}>
          <input type="checkbox" checked={kinds.has(k)} onchange={() => toggleKind(k)} />
          <span class="dot"></span>{k}
        </label>
      {/each}
    </div>
    <GraphView title={doc.title} entities={shown} {selected} onselect={(id) => (selected = id)} {countFor} />
    <p class="muted small">
      {shown.length} of {visible.length} entities shown{item ? ` for item ${item}` : ""}. Dashed lines are unclassified names: nothing says what they are.
      Boxes along the bottom are other documents that mention the same name.
    </p>

    <div class="prov" aria-live="polite">
      {#if chosen}
        <h2>{chosen.name} <span class="pill kind-{chosen.kind}">{chosen.kind}</span>
          {#if !chosen.verified && chosen.kind !== "Person"}<span class="pill unverified">not verified against CVR</span>{/if}</h2>
        {#if alsoIn.length > 0}
          <p class="also">Also in:
            {#each alsoIn as o, i (o.url)}<a href="/doc/{toId(o.url)}">{i ? ", " : ""}{o.source} · {o.title}</a>{/each}
          </p>
        {/if}
        <ul class="mentions">
          {#each chosen.mentions.filter((m) => !item || m.item === item) as m, i (i)}
            {@const [pre, hit, post] = split(m.snippet, chosen.name)}
            <li>
              <div class="meta">item {m.item} · {m.method} · confidence {m.confidence}</div>
              <blockquote>{pre}{#if hit}<mark>{hit}</mark>{/if}{post}</blockquote>
              <div class="meta">
                fetched {stamp(m.fetchedAt)} · sha256 <code>{m.sha256.slice(0, 12)}</code> ·
                <a href={m.sourceUrl} target="_blank" rel="noreferrer">source page</a>
              </div>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">Click a node to see every sentence it was found in, with the page, time and hash it came from.</p>
      {/if}
    </div>
  </section>
</div>
