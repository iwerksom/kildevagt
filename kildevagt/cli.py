"""Command line: kildevagt run | status | diff"""
import argparse
import os
from collections import Counter
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from .adapters import load_adapter
from .archive import Archive
from .fetch import BudgetExceeded, Fetcher
from .health import GREEN, RED, YELLOW, Health, baseline, evaluate
from .pipeline import run_source

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "archive"
SOURCES_DIR = ROOT / "sources"
sys.path.insert(0, str(ROOT))  # lets sources/*.yaml point at Python adapters in sources/


COLOURS = {"GREEN": "32", "YELLOW": "33", "RED": "31", "BLOCKED": "35"}


def badge(status: str) -> str:
    if not sys.stdout.isatty() and not os.environ.get("FORCE_COLOR"):
        return f"[{status}]"
    return f"\033[1;{COLOURS.get(status, '0')}m[{status}]\033[0m"


def cmd_run(args):
    archive = Archive(ARCHIVE_DIR)
    fetcher = Fetcher(max_requests=args.max_requests)
    since = date.today() - timedelta(days=args.days)
    run_id = archive.start_run()
    started = time.monotonic()
    paths = sorted(args.sources_dir.glob("*.yaml"))
    if args.source:
        paths = [p for p in paths if p.stem == args.source]
        if not paths:
            sys.exit(f"No source called {args.source!r} in {args.sources_dir}")
    exit_code = 0
    for path in paths:
        adapter = load_adapter(path, fetcher)
        listing_error = None
        try:
            found, counts, errors, checked, problems = run_source(adapter, archive, run_id, since, args.force)
        except BudgetExceeded as error:
            print(f"STOPPED: {error}")
            exit_code = 2
            break
        except Exception as error:  # a broken or blocked source is reported, the others still run
            found, counts, errors, checked, problems = 0, Counter(), [], 0, []
            listing_error = f"{type(error).__name__}: {error}"
            errors = [listing_error]
        usual = baseline(archive.previous_item_counts(adapter.source_id))
        health = evaluate(found, usual, checked, len({p.split(": ")[0] for p in problems}), listing_error)
        if errors and not listing_error and health.status == GREEN:
            health = Health(YELLOW, [f"{len(errors)} item errors"])
        archive.record_source(run_id, adapter.source_id, found, counts, errors, checked,
                              len({p.split(": ")[0] for p in problems}), health.status, health.reasons)
        print(f"{badge(health.status)} {adapter.source_id}: {found} items, new={counts['new']} "
              f"changed={counts['changed']} unchanged={counts['unchanged']} cached={counts['cached']}")
        for reason in health.reasons:
            print(f"    why: {reason}")
        for problem in problems[:3]:
            print(f"    page: {problem}")
        for error in errors:
            if error != listing_error:
                print(f"    ! {error}")
        if health.status == RED:
            exit_code = exit_code or 1
    archive.finish_run(run_id, fetcher.request_count)
    print(f"{fetcher.request_count} requests in {time.monotonic() - started:.0f}s")
    return exit_code


def cmd_status(args):
    archive = Archive(ARCHIVE_DIR)
    rows = archive.db.execute(
        "SELECT rs.*, r.started_at FROM run_sources rs JOIN runs r ON r.id = rs.run_id "
        "WHERE rs.run_id = (SELECT MAX(run_id) FROM run_sources x WHERE x.source_id = rs.source_id) "
        "ORDER BY rs.source_id").fetchall()  # the newest run of each source
    if not rows:
        print("No runs yet. Try: kildevagt run")
        return 0
    for row in rows:
        health = row["health"] or "UNKNOWN"
        print(f"{badge(health)} {row['source_id']:12} run {row['run_id']} at {row['started_at'][:19]}  "
              f"items={row['items_found']} new={row['new']} changed={row['changed']} unchanged={row['unchanged']}")
        for reason in (row["health_reasons"] or "").splitlines():
            print(f"      why: {reason}")
    totals = archive.db.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT url) urls, (SELECT SUM(requests) FROM runs) req "
        "FROM fetches").fetchone()
    print(f"archive: {totals['n']} fetches of {totals['urls']} URLs, {totals['req']} requests in total")
    return 1 if any(r["health"] == RED for r in rows) else 0


def cmd_numbers(args):
    """The numbers to remember for the interview."""
    archive = Archive(ARCHIVE_DIR)
    one = lambda sql: archive.db.execute(sql).fetchone()[0]
    sources = sorted(args.sources_dir.glob("*.yaml"))
    last = {r["source_id"]: r["health"] for r in archive.db.execute(
        "SELECT source_id, health FROM run_sources rs WHERE run_id = "
        "(SELECT MAX(run_id) FROM run_sources x WHERE x.source_id = rs.source_id)")}
    size = sum(f.stat().st_size for f in ARCHIVE_DIR.rglob("*") if f.is_file()) / 1e6
    print(f"sources                {len(sources)} configured, {sum(1 for h in last.values() if h == 'BLOCKED')} blocked by robots.txt")
    print(f"meetings archived      {one(chr(83)+'ELECT COUNT(DISTINCT url) FROM fetches WHERE kind=' + chr(39)+'meeting'+chr(39))}")
    print(f"agenda PDFs archived   {one('SELECT COUNT(DISTINCT url) FROM fetches WHERE kind=' + chr(39)+'pdf'+chr(39))}")
    print(f"archive size           {size:.0f} MB")
    print(f"HTTP requests, total   {one('SELECT SUM(requests) FROM runs')} in {one('SELECT COUNT(*) FROM runs')} runs")
    print(f"time of runs, total    {one('SELECT CAST(SUM((julianday(finished_at)-julianday(started_at))*86400) AS INT) FROM runs WHERE finished_at IS NOT NULL')} s")
    try:
        from .graph import neo4j_driver
        driver = neo4j_driver(ROOT)
        with driver.session() as session:
            for label in ("Document", "AgendaItem", "Company", "Organisation", "Person", "Place"):
                n = session.run(f"MATCH (n:{label}) RETURN count(n) AS n").single()["n"]
                print(f"graph nodes {label:12} {n}")
            edges = session.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
            bare = session.run("MATCH ()-[r]->() WHERE r.sha256 IS NULL OR r.source_url IS NULL "
                               "OR r.fetched_at IS NULL OR r.snippet IS NULL RETURN count(r) AS n").single()["n"]
            print(f"graph edges            {edges} ({bare} without full provenance)")
        driver.close()
    except Exception as error:
        print(f"graph                  not available ({type(error).__name__}); start Neo4j and run: kildevagt graph")
    return 0


def cmd_diff(args):
    archive = Archive(ARCHIVE_DIR)
    rows = archive.db.execute(
        "SELECT * FROM fetches WHERE run_id = (SELECT MAX(id) FROM runs) "
        "AND change IN ('new','changed') AND kind != 'listing' ORDER BY doc_date").fetchall()
    for row in rows:
        print(f"{row['change']:8} {row['kind']:8} {row['doc_date'] or '':10} {row['url']}")
        print(f"         sha256 {row['sha256'][:16]}…  fetched {row['fetched_at'][:19]}")
    if not rows:
        print("Nothing new or changed in the last run.")
    return 0


def cmd_graph(args):
    from .graph import build_graph
    totals = build_graph(Archive(ARCHIVE_DIR), args.sources_dir, ROOT)
    for key, value in totals.items():
        print(f"{key:26} {value}")
    print(f"hard cases logged in {ARCHIVE_DIR / 'entity_log.jsonl'}")
    return 0


def cmd_query(args):
    from .graph import neo4j_driver
    queries = {p.stem: p for p in sorted((ROOT / "queries").glob("*.cypher"))}
    if args.name == "list" or args.name not in queries:
        for name, path in queries.items():
            print(f"{name}\n    {path.read_text().splitlines()[0][3:]}")
        return 0 if args.name == "list" else 1
    params = dict(p.split("=", 1) for p in args.param)
    params.setdefault("since", "2000-01-01")
    params.setdefault("name", "")
    params.setdefault("meeting", "")
    driver = neo4j_driver(ROOT)
    with driver.session() as session:
        rows = [r.data() for r in session.run(queries[args.name].read_text(), **params)]
    driver.close()
    for row in rows:
        print(" | ".join(f"{k}={v}" for k, v in row.items()))
    print(f"({len(rows)} rows)")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="kildevagt")
    parser.add_argument("--sources-dir", type=Path, default=SOURCES_DIR,
                        help="folder with source configs (default: sources/)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="fetch, archive and detect changes")
    run.add_argument("--source", help="only this source (file name in sources/ without .yaml)")
    run.add_argument("--days", type=int, default=90, help="how far back to look (default 90)")
    run.add_argument("--force", action="store_true", help="ignore the fetch cache")
    run.add_argument("--max-requests", type=int, default=150, help="hard request budget")
    run.set_defaults(func=cmd_run)
    sub.add_parser("status", help="result of the last run").set_defaults(func=cmd_status)
    sub.add_parser("diff", help="new and changed documents in the last run").set_defaults(func=cmd_diff)
    sub.add_parser("numbers", help="the numbers to remember").set_defaults(func=cmd_numbers)
    sub.add_parser("graph", help="rebuild the Neo4j graph from the archive").set_defaults(func=cmd_graph)
    query = sub.add_parser("query", help="run a Cypher query from queries/ ('list' shows them)")
    query.add_argument("name")
    query.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    query.set_defaults(func=cmd_query)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(args.func(args))
