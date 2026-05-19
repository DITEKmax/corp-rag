---
phase: 05-retrieval-guards-query-api
artifact: user-setup
updated: 2026-05-19
---

# Phase 05 User Setup

Phase 05 live UAT requires a running local stack, an OpenRouter key, cached local embedding/reranker models, and a fresh indexed corpus. Mocked CI verification does not require these.

## Required Environment

Create or update ignored `infra/.env` from the repository root:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
```

Set these values in `infra/.env`:

```text
OPENROUTER_API_KEY=<openrouter-key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEEPSEEK_MODEL_ID=deepseek/deepseek-v4-flash:free
AI_RERANKER_ENABLED=true
AI_QUERY_TIMEOUT_SECONDS=30
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong-local-password>
```

The live query smoke tests also use local shell variables:

```powershell
$env:AI_QUERY_LIVE_SMOKE_ENABLED = "true"
$env:AI_QUERY_LIVE_CORPUS_READY = "true"
$env:AI_QUERY_LIVE_BASE_URL = "http://localhost:8000"
$env:OPENROUTER_API_KEY = "<openrouter-key>"
```

For the degraded Qdrant-off scenario only, set this after stopping Qdrant:

```powershell
$env:AI_QUERY_LIVE_DEGRADED_SMOKE_ENABLED = "true"
```

## Start The Stack

Run from the repository root. Do not run `docker compose down -v` before collecting UAT evidence.

```powershell
$Compose = @("compose", "--env-file", "infra/.env", "-f", "infra/docker-compose.yml")
docker @Compose up -d --build
docker @Compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/diagnostics
```

The `python-ai` service should keep the 4 GiB reservation and 6 GiB limit. First live query may load both `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`; keep the `bge-m3-cache` volume.

## Fresh Corpus Setup

Phase 04 deleted the TechCorp happy-path document, so Phase 05 retrieval UAT must upload a new document.

Create a small query-focused document:

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
@'
# TechCorp Phase 5 Query Policy

The HR department owns the vacation policy for TechCorp employees.
Employees receive annual vacation after manager approval.
The vacation policy is an internal HR policy and applies to all full-time employees.

The Security Operations Center depends on the Access Policy before granting privileged access.
The Compliance department counts policy exceptions every quarter.
'@ | Set-Content -Encoding UTF8 .tmp\phase5-query-policy.md
```

Log in to Java and upload the corpus:

```powershell
curl.exe -s -c .tmp\phase5-cookies.txt `
  -H "Content-Type: application/json" `
  -d "{`"username`":`"admin`",`"password`":`"<strong-local-password>`"}" `
  http://localhost:8080/api/v1/auth/login | ConvertFrom-Json

$doc = curl.exe -s -b .tmp\phase5-cookies.txt `
  -F "file=@.tmp\phase5-query-policy.md;type=text/markdown" `
  -F "title=TechCorp Phase 5 Query Policy" `
  -F "accessLevel=INTERNAL" `
  -F "department=HR" `
  -F "docType=POLICY" `
  -F "language=en" `
  http://localhost:8080/api/v1/documents | ConvertFrom-Json
$Phase5DocId = $doc.id
Start-Sleep -Seconds 120
```

Verify the corpus is indexed:

```powershell
$AiDbPassword = "corp_rag_ai"
$JavaDbPassword = "corp_rag_java_password"
$Neo4jPassword = "local-neo4j-password"

docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,title,status,chunk_count,neo4j_entity_count FROM documents WHERE id = '$Phase5DocId';"

docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id,status,last_failure_stage,last_failure_code FROM document_index_state WHERE document_id = '$Phase5DocId';"

docker @Compose exec -T neo4j cypher-shell -u neo4j -p $Neo4jPassword `
  "MATCH (d:Document {id: '$Phase5DocId'}) OPTIONAL MATCH (e:Entity)-[:MENTIONED_IN]->(d) RETURN d.id AS documentId, count(e) AS entities;"
```

## Run Optional Live Query Smokes

```powershell
cd ai-service
$env:AI_QUERY_LIVE_SMOKE_ENABLED = "true"
$env:AI_QUERY_LIVE_CORPUS_READY = "true"
$env:AI_QUERY_LIVE_BASE_URL = "http://localhost:8000"
$env:AI_QUERY_LIVE_DEPARTMENTS = "HR"
$env:AI_QUERY_LIVE_DOC_TYPES = "POLICY"
$env:OPENROUTER_API_KEY = "<openrouter-key>"
uv run pytest tests/test_query_live_smokes.py -m integration -q -s
cd ..
```

The degraded scenario is separate: stop Qdrant, set `AI_QUERY_LIVE_DEGRADED_SMOKE_ENABLED=true`, run only `test_live_query_qdrant_off_graph_degraded_smoke`, then start Qdrant again.

