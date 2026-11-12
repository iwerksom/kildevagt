<script lang="ts">
  import Viewer from "#lib/Viewer.svelte";
  let { data } = $props();
</script>

<svelte:head><title>{data.doc.title} · Kildevagt viewer</title></svelte:head>
<Viewer doc={data.doc} />
