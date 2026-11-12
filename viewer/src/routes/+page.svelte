<script lang="ts">
  import { toId } from "#lib/id.ts";
  let { data } = $props();
</script>

{#if data.error}
  <section class="notice">
    <h1>Cannot reach Neo4j</h1>
    <p>Start it with <code>docker compose up -d</code>, build the graph with <code>kildevagt graph</code>,
      and put the password in <code>viewer/.env.local</code>.</p>
    <p class="muted">{data.error}</p>
  </section>
{:else if data.docs.length === 0}
  <section class="notice"><h1>The graph is empty</h1><p>Run <code>kildevagt run</code> and then <code>kildevagt graph</code>.</p></section>
{:else}
  <section>
    <h1>Documents</h1>
    <table class="list">
      <thead><tr><th>Date</th><th>Source</th><th>Meeting</th><th>Items</th><th>Mentions</th><th>Status</th></tr></thead>
      <tbody>
        {#each data.docs as d (d.url)}
          <tr>
            <td>{d.date ?? "–"}</td>
            <td>{d.source}</td>
            <td><a href="/doc/{toId(d.url)}">{d.title}</a></td>
            <td>{d.items}</td>
            <td>{d.mentions}</td>
            <td><span class="pill {d.change}">{d.change}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{/if}
