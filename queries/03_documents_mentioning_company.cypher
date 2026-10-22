// All documents that mention a company, each with its source link, the exact words and a hash.
// Param: name (part of the company name, e.g. "vand")
MATCH (d:Document)-[r:MENTIONS]->(c)
WHERE (c:Company OR c:Organisation)
  AND toLower(c.name) CONTAINS toLower($name)
RETURN labels(c)[0] AS kind, c.name AS company, d.title AS meeting, r.item AS agenda_item, r.snippet AS found_in_text,
       r.confidence AS confidence, r.method AS method,
       r.source_url AS source_url, r.fetched_at AS fetched_at, left(r.sha256, 12) AS sha256
ORDER BY d.title, r.item
