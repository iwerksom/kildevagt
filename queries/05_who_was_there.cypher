// Elected members who ATTENDED a meeting (only where the page says nobody was absent),
// with the page they were read from. Param: meeting (part of the meeting title)
MATCH (p:Person)-[r:ATTENDED]->(m:Meeting)
WHERE toLower(m.title) CONTAINS toLower($meeting)
RETURN m.date AS date, p.name AS member, p.party AS party, r.source_url AS source_url,
       left(r.sha256, 12) AS sha256
ORDER BY date DESC, member
LIMIT 40
