// Which companies are mentioned by more than one municipality?
// Company = has a legal form (A/S, ApS ...). Organisation = a name spaCy guessed, unverified.
// This is the "one core, many newsrooms" question: patterns no single newsroom can see.
MATCH (s:Source)-[:PUBLISHES]->(d:Document)-[r:MENTIONS]->(c)
WHERE c:Company OR c:Organisation
WITH c, collect(DISTINCT s.id) AS municipalities, count(r) AS mentions
WHERE size(municipalities) > 1
RETURN labels(c)[0] AS kind, c.name AS name, municipalities, mentions
ORDER BY kind, mentions DESC
