# Kildevagt viewer

A small Next.js page: pick a document, see its agenda on the left and the graph of what it
mentions on the right. Click a node to read every sentence it was found in, with the page, time and
SHA-256 it came from. Other documents that mention the same name show up along the bottom, so you can
see a company that appears in more than one place.

It only **reads** the Neo4j graph; nothing here writes data.

```bash
docker compose up -d && .venv/bin/kildevagt graph     # from the repo root: start Neo4j, build the graph
cd viewer
cp .env.local.example .env.local                      # same password as NEO4J_PASSWORD in ../.env
npm install
npm run dev                                           # http://127.0.0.1:3000
```

Production check: `npm run build && npm start`. Type check: `npm run typecheck`.

## What it shows, and what it does not

- Node colour = kind. **Company** has a legal form (A/S, ApS ...). **Organisation** is a name spaCy guessed and is
  unverified (dashed lines). **Person** is an elected official only. **Place** is hidden by default because it is noisy.
- Click an agenda item to show only the entities found in that item.
- Neo4j is bound to `127.0.0.1` and the viewer reads it on the server; the browser never sees the password.
- Not built: search, editing, CVR links, authentication. It is meant to run on one machine.
- Layout is a simple ring, not a force simulation, so with many entities some labels overlap. It shows the 24 most mentioned.
