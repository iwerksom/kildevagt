<script lang="ts">
  import "../app.css";
  let { children } = $props();
</script>

<svelte:head>
  <title>Kildevagt viewer</title>
  <meta name="description" content="A document beside its graph neighbourhood, with the source of every link." />
</svelte:head>

<header class="top">
  <a href="/" class="brand">Kildevagt</a>
  <span class="muted">every link points back to the page it came from</span>
</header>
<main>{@render children()}</main>
