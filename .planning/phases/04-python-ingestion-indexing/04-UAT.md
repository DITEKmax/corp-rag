---
status: partial
phase: 04-python-ingestion-indexing
source: ["04-08-PLAN.md"]
started: "2026-05-17T00:00:00Z"
updated: "2026-05-17T00:00:00Z"
---

# Phase 4 End-to-End UAT

This script validates the completed Python ingestion and indexing path against the retained local Docker volumes from earlier phases.

## Preconditions

- Do not run `docker compose down -v`, data reset scripts, or any volume cleanup before Scenario 1. The retained RabbitMQ queues and databases are part of the test.
- Docker Desktop must have enough memory for the stack plus local bge-m3. The `python-ai` service reserves 3 GB and is capped at 4 GB.
- `OPENROUTER_API_KEY` must be set for the DeepSeek/OpenRouter structured-output preflight and graph extraction scenarios.
- Keep all IDs and command outputs that prove each scenario in the Evidence Log section.

## Shared PowerShell Variables

Run from the repository root.

```powershell
$Compose = @("compose", "--env-file", "infra/.env", "-f", "infra/docker-compose.yml")
$RabbitUser = "corp_rag"
$RabbitPassword = "corp_rag_password"
$RabbitAuth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${RabbitUser}:${RabbitPassword}"))
$Headers = @{ Authorization = "Basic $RabbitAuth" }
$JavaDbPassword = "corp_rag_java_password"
$AiDbPassword = "corp_rag_ai"
$Neo4jPassword = "local-neo4j-password"
New-Item -ItemType Directory -Force .tmp | Out-Null
```

Create an ignored local env file before the first stack start:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
```

Edit `infra/.env` and set:

```text
OPENROUTER_API_KEY=<openrouter-key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEEPSEEK_MODEL_ID=deepseek/deepseek-v4-flash:free
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong-local-password>
```

## P1 FlagEmbedding Smoke

This intentionally loads local `BAAI/bge-m3` and verifies one dense+sparse inference.

```powershell
cd ai-service
$env:AI_EMBEDDING_LIVE_SMOKE_ENABLED = "true"
uv run pytest tests/test_live_smokes.py::test_live_flagembedding_bge_m3_dense_sparse_preflight -m integration -q -s
cd ..
```

Expected:

- Dense vector dimension is `1024`.
- Sparse lexical weights are non-empty.
- First run may download model weights into the Hugging Face cache; later runs should reuse the cache.

## P2 DeepSeek/OpenRouter Smoke

```powershell
cd ai-service
$env:OPENROUTER_API_KEY = "<openrouter-key>"
uv run pytest tests/test_deepseek_extraction_live.py::test_live_deepseek_extracts_expected_hr_policy_subset -m integration -q -s
cd ..
```

Expected:

- The test runs instead of skipping.
- The response contains the HR department, remote work policy, and `OWNS` relation subset.

## P3 Retained-Volume Docker Startup

Start the stack without deleting volumes:

```powershell
docker @Compose up -d --build
docker @Compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:6333/collections/documents_chunks
```

Check RabbitMQ retained queues before and after Python consumes messages:

```powershell
Invoke-RestMethod -Headers $Headers http://localhost:15672/api/queues/%2F/ai.document.uploaded |
  Select-Object name,messages,messages_ready,messages_unacknowledged
Invoke-RestMethod -Headers $Headers http://localhost:15672/api/queues/%2F/ai.document.deleted |
  Select-Object name,messages,messages_ready,messages_unacknowledged
Invoke-RestMethod -Headers $Headers http://localhost:15672/api/queues/%2F/backend.document.failed |
  Select-Object name,messages,messages_ready,messages_unacknowledged
```

Check AI Postgres state:

```powershell
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT event_type, count(*) FROM processed_events GROUP BY event_type ORDER BY event_type;"
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id,status,last_indexed_event_id,last_failure_stage,last_failure_code FROM document_index_state ORDER BY updated_at DESC LIMIT 10;"
```

Check Java document status:

```powershell
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,title,status,chunk_count,neo4j_entity_count,failure_stage,failure_error_code,deleted_at FROM documents ORDER BY uploaded_at DESC LIMIT 10;"
```

Check Neo4j:

```powershell
docker @Compose exec -T neo4j cypher-shell -u neo4j -p $Neo4jPassword `
  "MATCH (d:Document) OPTIONAL MATCH (e:Entity)-[:MENTIONED_IN]->(d) RETURN d.id AS documentId, d.title AS title, count(e) AS entities ORDER BY title LIMIT 10;"
```

Expected:

- `python-ai`, `java-backend`, RabbitMQ, Qdrant, Neo4j, MinIO, and Postgres are healthy.
- The Qdrant collection exists with named dense and sparse vectors.
- Retained messages are consumed, not deleted manually.

## Create UAT Fixtures

Generate a small valid two-page PDF and one intentionally broken PDF:

```powershell
@'
from pathlib import Path

def pdf_text(text):
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
    return f"<< /Length {len(body.encode('latin-1'))} >>\nstream\n{body}\nendstream"

objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 6 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
    pdf_text("Remote Work Policy. The HR Department owns remote work approvals."),
    pdf_text("Employees submit remote work requests in Workday before travel."),
]

data = bytearray(b"%PDF-1.4\n")
offsets = [0]
for number, obj in enumerate(objects, start=1):
    offsets.append(len(data))
    data.extend(f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
xref = len(data)
data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
for offset in offsets[1:]:
    data.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
data.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1"))

Path(".tmp").mkdir(exist_ok=True)
Path(".tmp/phase4-policy.pdf").write_bytes(data)
Path(".tmp/phase4-broken.pdf").write_text("%PDF-1.4\nnot a valid document body", encoding="ascii")
'@ | python -
```

Log in and keep a cookie jar:

```powershell
curl.exe -s -c .tmp\phase4-cookies.txt `
  -H "Content-Type: application/json" `
  -d "{`"username`":`"admin`",`"password`":`"<strong-local-password>`"}" `
  http://localhost:8080/api/v1/auth/login | ConvertFrom-Json
```

## Scenario 1 - Consume Accumulated Phase 3 Messages

After P3 startup, wait up to two minutes and query state:

```powershell
Start-Sleep -Seconds 120
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT event_type, count(*) FROM processed_events GROUP BY event_type ORDER BY event_type;"
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id,status,last_failure_stage,last_failure_code FROM document_index_state ORDER BY updated_at DESC LIMIT 10;"
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,title,status,chunk_count,neo4j_entity_count,failure_stage,failure_error_code,deleted_at FROM documents ORDER BY uploaded_at DESC LIMIT 10;"
Invoke-RestMethod -Headers $Headers http://localhost:15672/api/queues/%2F/backend.document.failed |
  Select-Object name,messages,messages_ready,messages_unacknowledged
```

Expected:

- Three retained events are terminal in AI `processed_events`.
- AI `document_index_state` includes one indexed document and one deleted tombstone.
- Java document status/audit reflects the indexed terminal event.
- `backend.document.failed` has no unexpected messages.

## Scenario 2 - Fresh PDF Happy Path

Upload the generated PDF:

```powershell
$happy = curl.exe -s -b .tmp\phase4-cookies.txt `
  -F "file=@.tmp\phase4-policy.pdf;type=application/pdf" `
  -F "title=Phase 4 Happy Path Policy" `
  -F "accessLevel=INTERNAL" `
  -F "department=HR" `
  -F "docType=POLICY" `
  -F "language=en" `
  http://localhost:8080/api/v1/documents | ConvertFrom-Json
$happyId = $happy.id
$happyId
Start-Sleep -Seconds 180
```

Verify Java status, Qdrant points, Neo4j graph data, and parent rows:

```powershell
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,status,chunk_count,neo4j_entity_count,qdrant_collection,indexing_duration_ms FROM documents WHERE id = '$happyId';"

$qdrantBody = @{
  filter = @{ must = @(@{ key = "documentId"; match = @{ value = $happyId } }) }
  limit = 10
  with_payload = $true
  with_vector = $false
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://localhost:6333/collections/documents_chunks/points/scroll -ContentType application/json -Body $qdrantBody

docker @Compose exec -T neo4j cypher-shell -u neo4j -p $Neo4jPassword `
  "MATCH (d:Document {id: '$happyId'}) OPTIONAL MATCH (e:Entity)-[:MENTIONED_IN]->(d) OPTIONAL MATCH (r:RelationMention)-[:EVIDENCE]->(d) RETURN d.id AS documentId, count(DISTINCT e) AS entities, count(DISTINCT r) AS relations;"

docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id, count(*) AS parent_chunks FROM document_chunks_parent WHERE document_id = '$happyId' GROUP BY document_id;"
```

Expected:

- Java status is `INDEXED`.
- `chunk_count` is greater than 0.
- `neo4j_entity_count` is at least 1.
- Qdrant payload includes `chunkId`, `parentChunkId`, `documentId`, `documentTitle`, `sectionPath`, `content`, `language`, `docType`, `department`, `accessLevel`, `isSanitized`, and `sanitizerFlags`.
- Neo4j has `Document`, `Entity`, and `RelationMention` evidence for the document.
- AI Postgres has parent chunk rows.

## Scenario 3 - Broken PDF Parsing Failure

```powershell
$broken = curl.exe -s -b .tmp\phase4-cookies.txt `
  -F "file=@.tmp\phase4-broken.pdf;type=application/pdf" `
  -F "title=Phase 4 Broken PDF" `
  -F "accessLevel=INTERNAL" `
  -F "department=HR" `
  -F "docType=POLICY" `
  -F "language=en" `
  http://localhost:8080/api/v1/documents | ConvertFrom-Json
$brokenId = $broken.id
Start-Sleep -Seconds 120

docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,status,failure_stage,failure_error_code,failure_retryable FROM documents WHERE id = '$brokenId';"
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id,status,last_failure_stage,last_failure_code FROM document_index_state WHERE document_id = '$brokenId';"
```

Expected:

- Java status is `FAILED`.
- Failure is `PARSING / INVALID_FILE_FORMAT / retryable=false`.
- AI state is `FAILED` with terminal `processed_events`.
- Qdrant and Neo4j have no artifacts for `$brokenId`.

## Scenario 4 - Neo4j Down Graph Rollback

```powershell
docker @Compose stop neo4j
$graphFail = curl.exe -s -b .tmp\phase4-cookies.txt `
  -F "file=@.tmp\phase4-policy.pdf;type=application/pdf" `
  -F "title=Phase 4 Graph Rollback Policy" `
  -F "accessLevel=INTERNAL" `
  -F "department=HR" `
  -F "docType=POLICY" `
  -F "language=en" `
  http://localhost:8080/api/v1/documents | ConvertFrom-Json
$graphFailId = $graphFail.id
Start-Sleep -Seconds 180

docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,status,failure_stage,failure_error_code,failure_retryable FROM documents WHERE id = '$graphFailId';"

$rollbackBody = @{
  filter = @{ must = @(@{ key = "documentId"; match = @{ value = $graphFailId } }) }
  limit = 10
  with_payload = $true
  with_vector = $false
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://localhost:6333/collections/documents_chunks/points/scroll -ContentType application/json -Body $rollbackBody

docker @Compose up -d neo4j
```

Expected:

- Java status is `FAILED`.
- Failure is `GRAPH_UPSERT / DEPENDENCY_UNAVAILABLE / retryable=true`.
- Qdrant scroll returns zero points for `$graphFailId`.
- Neo4j is restarted before continuing.

## Scenario 5 - Duplicate Redelivery Through RabbitMQ UI

Export the original uploaded event for `$happyId` from Java outbox:

```powershell
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -At -c "SELECT payload::text FROM outbox_events WHERE aggregate_id = '$happyId' AND event_type = 'document.uploaded' ORDER BY created_at DESC LIMIT 1;" > .tmp\duplicate-upload-payload.json
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -At -c "SELECT headers::text FROM outbox_events WHERE aggregate_id = '$happyId' AND event_type = 'document.uploaded' ORDER BY created_at DESC LIMIT 1;" > .tmp\duplicate-upload-headers.json
Get-Content .tmp\duplicate-upload-payload.json
Get-Content .tmp\duplicate-upload-headers.json
```

Open RabbitMQ Management at `http://localhost:15672`, log in as `corp_rag` / `corp_rag_password`, go to Exchanges, open `corp-rag.documents`, and use Publish message:

- Routing key: `document.uploaded`
- Payload: contents of `.tmp\duplicate-upload-payload.json`
- Properties: `content_type=application/json`, `delivery_mode=2`
- Headers: copy the same `x-correlation-id`, `x-event-type`, and `x-event-version` values from `.tmp\duplicate-upload-headers.json`

After publishing:

```powershell
Start-Sleep -Seconds 30
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT event_id,event_type,consumed_at FROM processed_events WHERE event_id = ((SELECT payload->'metadata'->>'eventId' FROM outbox_events WHERE aggregate_id = '$happyId' AND event_type = 'document.uploaded' ORDER BY created_at DESC LIMIT 1)::uuid);"
docker @Compose exec -T -e PGPASSWORD=$JavaDbPassword postgres `
  psql -U corp_rag_java -d corp_rag_java -c "SELECT id,status,chunk_count,neo4j_entity_count FROM documents WHERE id = '$happyId';"
Invoke-RestMethod -Headers $Headers http://localhost:15672/api/queues/%2F/backend.document.indexed |
  Select-Object name,messages,messages_ready,messages_unacknowledged
```

Expected:

- Python ACKs the duplicate.
- No new Qdrant or Neo4j work is created.
- Java document status and chunk/entity counts are unchanged.
- No extra indexed event is published for the duplicate.

## Scenario 6 - Optional Delete Cleanup

```powershell
curl.exe -s -b .tmp\phase4-cookies.txt -X DELETE http://localhost:8080/api/v1/documents/$happyId
Start-Sleep -Seconds 120
docker @Compose exec -T -e PGPASSWORD=$AiDbPassword postgres `
  psql -U corp_rag_ai -d corp_rag_ai -c "SELECT document_id,status FROM document_index_state WHERE document_id = '$happyId';"

$deleteBody = @{
  filter = @{ must = @(@{ key = "documentId"; match = @{ value = $happyId } }) }
  limit = 10
  with_payload = $true
  with_vector = $false
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://localhost:6333/collections/documents_chunks/points/scroll -ContentType application/json -Body $deleteBody

docker @Compose exec -T neo4j cypher-shell -u neo4j -p $Neo4jPassword `
  "MATCH (d:Document {id: '$happyId'}) RETURN count(d) AS documents;"
```

Expected:

- AI state is `DELETED`.
- Qdrant returns zero points for `$happyId`.
- Neo4j returns zero `Document` nodes for `$happyId`.

## Evidence Log

Fill this table during the run.

| Item | Value |
|---|---|
| P1 FlagEmbedding result | |
| P2 DeepSeek/OpenRouter result | |
| P3 stack start timestamp | |
| Scenario 1 retained processed count | |
| Scenario 2 happy document ID | |
| Scenario 2 indexed event ID | |
| Scenario 3 broken document ID | |
| Scenario 3 failed event ID | |
| Scenario 4 graph rollback document ID | |
| Scenario 4 failed event ID | |
| Scenario 5 duplicate event ID | |
| Scenario 6 delete document ID | |

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
