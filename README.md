# Kildevagt

A prototype of **one scraper core shared by many sources**, built to learn what a scraper for
several newsrooms really has to solve. It fetches council agendas and minutes (*dagsordener og
referater*) from Danish municipalities, archives everything with a hash, finds companies and elected
officials, and puts them in a graph where every edge points back to the page it came from.

It is a prototype. This is what it does and does not do today.

| Works | Does not work / not built |
|---|---|
| Two live sources: a plain-HTML one (YAML config only) and an AJAX one (small Python adapter), city councils | A third source (FirstAgenda) is **blocked on purpose** (see below). No third live source |
| Polite fetching, archive with SHA-256, change detection, per-source health (green/yellow/red/blocked) | CVR lookup: every company is `verified=false`. The classifier is rule-based: about 100% precision on its labelled names but only about 70 to 100% recall, see `tests/test_orgclass.py` |
| Entities (spaCy `da_core_news_lg` plus evidence rules: a name is a Company, an Organisation or Unclassified) and a Neo4j graph with provenance on every edge | Local-model clean-up of entities |
| 26 offline tests on saved pages; a read-only graph viewer in `viewer/` (Next.js, see its README) | Agenda annexes (bilag) are not fetched, only the main agenda PDF; no OCR |

**FirstAgenda**, a commercial agenda system used by several large municipalities, loads its data from
`/api`, and the `robots.txt` of those sites says `Disallow: /api`. The adapter therefore reports the
source as `BLOCKED` and never calls it. Access needs permission from the municipality or the vendor.

## Set up

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,graph]"
.venv/bin/python -m spacy download da_core_news_lg
cp .env.example .env            # set KILDEVAGT_CONTACT (your email, used in the User-Agent) and a Neo4j password
docker compose up -d            # Neo4j Community on localhost:7474 (browser) / 7687 (bolt)
```

## Use

```bash
.venv/bin/kildevagt run                      # fetch, archive, detect changes, check health
.venv/bin/kildevagt status                   # green / yellow / red / blocked per source
.venv/bin/kildevagt diff                     # what is new or changed in the last run
.venv/bin/kildevagt graph                    # rebuild the Neo4j graph from the archive (no requests)
.venv/bin/kildevagt query list               # the prepared Cypher queries in queries/
.venv/bin/kildevagt query 03_documents_mentioning_company --param name="reno djurs"
.venv/bin/kildevagt numbers                  # sources, documents, entities, edges, requests
demo/break_selector.sh                       # break a CSS selector on purpose and watch it go red
.venv/bin/pytest                             # offline tests
```

`kildevagt run` exits with code 1 if any source is red, so a cron job or CI step notices.

## How it works

```
sources/*.yaml          one file per source (selectors) ... and sources/<name>.py only when logic is needed
kildevagt/fetch.py      robots.txt, <= ~1 request/second/host, User-Agent with contact, retries, request budget
kildevagt/archive.py    raw bytes saved as sent + url + fetched_at + SHA-256 (SQLite + files under archive/)
kildevagt/adapters.py   the interface: list_items(since), fetch(item), parse(raw) -> Document
kildevagt/pipeline.py   run one source; check every archived page for missing fields
kildevagt/health.py     the rules for green / yellow / red / blocked
kildevagt/entities.py   companies, places, elected officials; privacy rules
kildevagt/graph.py      Neo4j; provenance (source_url, fetched_at, sha256, snippet) on every edge
```

Change detection compares a hash of the **extracted** content, not the raw bytes, because pages
contain noise. A page that could not be read properly gets the status `unreadable` and is never used
as a baseline, so a broken selector cannot look like the site changing.

## Add source number 4 (about 30 minutes)

1. **Check permission first (5 min).** Read `https://<host>/robots.txt` and the site's terms. If
   the data comes from a path that is disallowed, stop; do not work around it.
2. **Look at the page (10 min).** View source. If the meeting list is in the HTML, use a YAML file.
   If the page is an empty shell filled by JavaScript, open the browser's network tab and see
   which public URLs it calls; that is a Python adapter (copy `sources/syddjurs.py`).
3. **Write the config (10 min).** `cp sources/_template.yaml.example sources/<name>.yaml` and fill in the
   selectors. Run `kildevagt run --source <name>`; expect `[GREEN]` and a plausible item count.
4. **Add a test (5 min).** Save a listing page and one meeting page into `tests/fixtures/`, and copy
   `tests/test_hedensted.py`. The test should assert the dates and the number of agenda items.

Things that will bite: a selector that also matches non-meeting links, future meetings that are
published empty, a session cookie the site requires first, and pagination.

## Rules this project follows

- **Polite:** `robots.txt` respected, about one request per second per host, a User-Agent that names
  the project and gives a contact address, a hard request budget (default 150 per run), caching.
- **Privacy:** only companies, places and **elected officials** become nodes. Other person names found
  by spaCy are counted and dropped, and removed from stored text snippets (`[navn fjernet]`).
  Public documents still fall under GDPR; agenda items about individuals are the weak spot, because
  only names are removed, not whole agenda items.
- **No secrets, no data:** the Neo4j password is in `.env`, and `.env` and the downloaded `archive/` are in `.gitignore`.
