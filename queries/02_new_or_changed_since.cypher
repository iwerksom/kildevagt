// Everything that is new or changed since a date. Param: since (ISO date, e.g. 2026-10-01)
MATCH (d:Document)
WHERE d.last_change IN ['new', 'changed'] AND d.fetched_at >= $since
RETURN d.source_id AS source, d.title AS title, d.last_change AS change,
       d.fetched_at AS fetched_at, d.url AS url
ORDER BY d.fetched_at DESC
