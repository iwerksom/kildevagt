// The most mentioned companies, with how sure we are and whether they are verified against CVR.
MATCH (d:Document)-[r:MENTIONS]->(c:Company)
RETURN c.name AS company, c.legal_form AS legal_form, count(r) AS mentions,
       count(DISTINCT d) AS documents, max(r.confidence) AS best_confidence, c.verified AS cvr_verified
ORDER BY mentions DESC, company
LIMIT 15
