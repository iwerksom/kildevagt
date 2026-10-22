import { listDocuments, toId } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Home() {
  let docs;
  try {
    docs = await listDocuments();
  } catch (error) {
    return (
      <section className="notice">
        <h1>Cannot reach Neo4j</h1>
        <p>Start it with <code>docker compose up -d</code>, build the graph with <code>kildevagt graph</code>,
        and put the password in <code>viewer/.env.local</code>.</p>
        <p className="muted">{String(error)}</p>
      </section>
    );
  }
  if (docs.length === 0) {
    return <section className="notice"><h1>The graph is empty</h1><p>Run <code>kildevagt run</code> and then <code>kildevagt graph</code>.</p></section>;
  }
  return (
    <section>
      <h1>Documents</h1>
      <table className="list">
        <thead><tr><th>Date</th><th>Source</th><th>Meeting</th><th>Items</th><th>Mentions</th><th>Status</th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.url}>
              <td>{d.date ?? "–"}</td>
              <td>{d.source}</td>
              <td><a href={`/doc/${toId(d.url)}`}>{d.title}</a></td>
              <td>{d.items}</td>
              <td>{d.mentions}</td>
              <td><span className={`pill ${d.change}`}>{d.change}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
