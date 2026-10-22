"""Build the Neo4j graph from the archive (offline: no new requests are made).

Every relationship carries provenance: source_url, fetched_at, sha256 and a snippet of text.
The graph is rebuilt from the archive each time, so it can never drift away from it.
"""
import json
import logging
from collections import defaultdict
from pathlib import Path

import spacy
from neo4j import GraphDatabase

from .adapters import load_adapter
from .entities import Mention, extract, member_name
from .models import RawResponse

log = logging.getLogger("kildevagt")
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)  # "constraint already exists" noise


def neo4j_driver(root: Path):
    env = {}
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    password = env.get("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("NEO4J_PASSWORD missing: copy .env.example to .env and run docker compose up -d")
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", password))
    driver.verify_connectivity()
    return driver


def latest_documents(archive, sources_dir: Path):
    """Yield (parsed Document, fetch row) for the newest archived copy of each meeting page."""
    rows = archive.db.execute(
        "SELECT * FROM fetches WHERE kind='meeting' AND id IN "
        "(SELECT MAX(id) FROM fetches WHERE kind='meeting' AND content_hash NOT LIKE 'bad:%' "
        "GROUP BY source_id, url)").fetchall()
    adapters = {}
    for path in sorted(sources_dir.glob("*.yaml")):
        adapter = load_adapter(path, fetcher=None)
        adapters[adapter.source_id] = adapter
    for row in rows:
        if row["source_id"] not in adapters:
            continue
        content = (archive.root / row["path"]).read_bytes()
        raw = RawResponse(row["url"], content, "text/html", 200, row["fetched_at"])
        yield adapters[row["source_id"]].parse(raw), row


def build_graph(archive, sources_dir: Path, root: Path) -> dict:
    nlp = spacy.load("da_core_news_lg")
    docs = list(latest_documents(archive, sources_dir))
    members = {}                                       # lower-case name -> 'Name (Party)'
    for doc, _ in docs:
        for member in doc.members:
            members[member_name(member)[0].casefold()] = member

    drivers = neo4j_driver(root)
    totals = {"documents": 0, "agenda_items": 0, "mentions": 0, "private_persons_dropped": 0,
              "public_bodies_skipped": 0, "noise_skipped": 0}
    kinds = defaultdict(int)
    surface_forms = defaultdict(set)                   # company key -> spellings seen
    weak = []                                          # low-confidence guesses, for the log
    pending = []                                       # (fetch row, agenda item number, mention), written after resolving
    with drivers.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        for doc, row in docs:
            prov = {"source_url": row["url"], "fetched_at": row["fetched_at"], "sha256": row["sha256"]}
            session.run(
                "MERGE (s:Source {id:$sid}) SET s.name=$sname "
                "CREATE (d:Document {url:$url, title:$title, sha256:$sha, fetched_at:$fetched,"
                " last_change:$change, source_id:$sid}) "
                "CREATE (m:Meeting {url:$url, title:$title, date:$date}) "
                "CREATE (s)-[:PUBLISHES {source_url:$url, fetched_at:$fetched, sha256:$sha,"
                " snippet:$title}]->(d) "
                "CREATE (m)-[:RECORDED_IN {source_url:$url, fetched_at:$fetched, sha256:$sha,"
                " snippet:$title}]->(d)",
                sid=doc.source_id, sname=doc.source_id, url=row["url"], title=doc.title, sha=row["sha256"],
                fetched=row["fetched_at"], change=row["change"],
                date=doc.date.isoformat() if doc.date else None)
            totals["documents"] += 1
            for item in doc.agenda_items:
                session.run(
                    "MATCH (m:Meeting {url:$url}) "
                    "CREATE (a:AgendaItem {id:$id, number:$number, title:$title})-[:PART_OF {"
                    "source_url:$url, fetched_at:$fetched, sha256:$sha, snippet:$snippet}]->(m)",
                    url=row["url"], id=f"{row['url']}#{item.number}", number=item.number,
                    title=item.title, fetched=row["fetched_at"], sha=row["sha256"],
                    snippet=f"{item.number}. {item.title}"[:200])
                totals["agenda_items"] += 1
                mentions, stats = extract(nlp, f"{item.title}. {item.text}", members)
                for k in ("private_persons_dropped", "public_bodies_skipped", "noise_skipped"):
                    totals[k] += stats[k]
                pending += [(row, item.number, m) for m in mentions]
            _write_members(session, doc, row)
        resolved = _resolve_by_legal_form([m for _, _, m in pending])
        for row, item_number, mention in pending:
            _write_mention(session, row, item_number, mention)
            totals["mentions"] += 1
            kinds[mention.kind] += 1
            if mention.kind in ("Company", "Organisation", "Unclassified"):
                surface_forms[mention.key].add(mention.name)
            if mention.kind == "Unclassified":
                weak.append(mention)
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.key IS UNIQUE")
    drivers.close()
    log_path = archive.root / "entity_log.jsonl"
    totals.update({f"mentions_{k.lower()}": v for k, v in sorted(kinds.items())})
    totals["resolved_by_legal_form"] = len(resolved)
    totals["entity_log_cases"] = _write_entity_log(log_path, surface_forms, weak, resolved)
    return totals


def _write_mention(session, row, item_number, mention: Mention):
    props = {"source_url": row["url"], "fetched_at": row["fetched_at"], "sha256": row["sha256"],
             "snippet": mention.snippet, "item": item_number, "method": mention.method,
             "confidence": mention.confidence}
    if mention.kind == "Company":
        node = "MERGE (e:Company {key:$key}) ON CREATE SET e.name=$name, e.verified=false, e.cvr=null " \
               "SET e.legal_form=coalesce($form, e.legal_form)"
    elif mention.kind in ("Place", "Organisation", "Unclassified"):
        node = f"MERGE (e:{mention.kind} {{key:$key}}) ON CREATE SET e.name=$name, e.verified=false"
    else:
        node = "MERGE (e:Person {key:$pkey}) ON CREATE SET e.name=$name, e.party=$party, e.role='elected'"
    session.run(f"MATCH (d:Document {{url:$url}}) {node} CREATE (d)-[:MENTIONS $props]->(e)",
                url=row["url"], key=mention.key, pkey=f"{row['source_id']}|{mention.key}",
                name=mention.name, form=mention.legal_form, party=mention.party, props=props)


def _write_members(session, doc, row):
    """Elected members of the meeting body. ATTENDED only if the page says nobody was absent."""
    certain = doc.absent_note.strip().lower() == "ingen fraværende"
    for member in doc.members:
        name, party = member_name(member)
        props = {"source_url": row["url"], "fetched_at": row["fetched_at"], "sha256": row["sha256"],
                 "snippet": f"Medlemmer: {member}; {doc.absent_note or 'fravær ikke oplyst'}"}
        for relation in (["MEMBER_OF", "ATTENDED"] if certain else ["MEMBER_OF"]):
            session.run(
                f"MATCH (m:Meeting {{url:$url}}) "
                f"MERGE (p:Person {{key:$pkey}}) ON CREATE SET p.name=$name, p.party=$party, p.role='elected' "
                f"CREATE (p)-[:{relation} $props]->(m)",
                url=row["url"], pkey=f"{row['source_id']}|{name.casefold()}", name=name, party=party,
                props=props)


def _resolve_by_legal_form(mentions: list[Mention]) -> dict[str, set[str]]:
    """'Hedensted Spildevand' and 'Hedensted Spildevand A/S' are one name. If any mention of a name
    carries a legal form, every mention of the same normalised name becomes a Company."""
    with_form = {m.key: m.legal_form for m in mentions if m.kind == "Company" and m.legal_form}
    resolved: dict[str, set[str]] = defaultdict(set)
    for m in mentions:
        if m.key in with_form and m.kind in ("Organisation", "Unclassified"):
            resolved[m.key].add(m.name)
            m.kind, m.legal_form, m.method = "Company", with_form[m.key], m.method + " (name has a legal form elsewhere)"
            m.confidence = max(m.confidence, 0.7)
    return resolved


def _write_entity_log(path: Path, surface_forms, weak, resolved=None) -> int:
    """Hard cases for entity resolution: one company under several spellings, and weak guesses."""
    cases = []
    for key, forms in sorted(surface_forms.items()):
        if len(forms) > 1:
            cases.append({"case": "merged_spellings", "key": key, "spellings": sorted(forms)})
    for key, names in sorted((resolved or {}).items()):
        cases.append({"case": "bare_name_merged_into_company_with_legal_form", "key": key, "names": sorted(names)})
    counts = defaultdict(int)
    for mention in weak:
        counts[mention.name] += 1
    for name, n in sorted(counts.items(), key=lambda x: -x[1]):
        cases.append({"case": "unclassified_no_evidence_for_any_kind", "name": name,
                      "mentions": n})
    path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases), encoding="utf-8")
    return len(cases)
