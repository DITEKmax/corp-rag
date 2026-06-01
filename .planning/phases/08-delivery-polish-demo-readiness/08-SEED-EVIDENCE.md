# Phase 8 Seed Corpus Evidence

- Success: `true`
- Corpus version: `ru-aviation-logistics-v1`
- Documents: `16/16`

## Compose Targets

- `java_base_url`: `http://localhost:8080`
- `qdrant_url`: `http://localhost:6333`
- `qdrant_collection`: `documents_chunks`
- `neo4j_uri`: `bolt://localhost:7687`
- `neo4j_database`: `neo4j`

## Java Documents

| Manifest ID | Java ID | Title | Status | Chunks | Indexed At |
|-------------|---------|-------|--------|--------|------------|
| CORP-RU-AV-001 | 337f4a65-efdc-4b3a-91a1-f2e3434439ca | Регламент передачи рейса | INDEXED | 1 | 2026-06-01T21:11:48.353805Z |
| CORP-RU-AV-002 | 1c45b64f-5aaa-451c-b675-1079181ff069 | Памятка по приоритетам груза | INDEXED | 1 | 2026-06-01T21:12:00.851015Z |
| CORP-RU-AV-003 | e6d8207a-460b-4f4f-a986-3dc143e51271 | Норматив топливного резерва | INDEXED | 1 | 2026-06-01T21:12:33.891279Z |
| CORP-RU-AV-004 | 22618bcb-ada0-497a-916c-e072110c70c5 | Отчет по окнам технического обслуживания | INDEXED | 1 | 2026-06-01T21:12:58.726487Z |
| CORP-RU-AV-005 | 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6 | Политика планирования экипажей | INDEXED | 1 | 2026-06-01T21:13:45.973668Z |
| CORP-RU-AV-006 | 43da091e-fcb9-4fde-8615-82518f4d452f | Руководство склада запасных частей | INDEXED | 1 | 2026-06-01T21:14:56.819941Z |
| CORP-RU-AV-007 | 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6 | Памятка по метеозадержкам | INDEXED | 1 | 2026-06-01T21:16:30.602389Z |
| CORP-RU-AV-008 | 33b3e4ed-755a-4646-8a68-3ea843e1fe24 | SLA наземного обслуживания | INDEXED | 1 | 2026-06-01T21:16:57.95427Z |
| CORP-RU-AV-009 | 805c11c2-d915-4ca9-b188-b1116020e13e | Руководство по таможенному транзиту | INDEXED | 1 | 2026-06-01T21:17:25.254739Z |
| CORP-RU-AV-010 | 1b7d28c7-3a05-4501-826f-ba36b8e8aaf4 | Политика безопасности аэропорта | INDEXED | 1 | 2026-06-01T21:18:07.023491Z |
| CORP-RU-AV-011 | 7b04026e-6663-4d40-b07a-6463b8afd19c | Норматив по опасным грузам | INDEXED | 1 | 2026-06-01T21:19:04.967768Z |
| CORP-RU-AV-012 | e30b55fe-d647-4563-99ce-d8820417f0c8 | Отчет по холодовой цепи | INDEXED | 1 | 2026-06-01T21:19:28.764117Z |
| CORP-RU-AV-013 | fa5c99e6-33d2-42ec-bb31-57630a765734 | Руководство по реагированию на инциденты | INDEXED | 1 | 2026-06-01T21:19:55.848113Z |
| CORP-RU-AV-014 | 7b953631-a816-494e-acc6-ac539086b9b4 | Отчет аудита поставщиков | INDEXED | 1 | 2026-06-01T21:20:25.173822Z |
| CORP-RU-AV-015 | 82ae8890-6b63-4cff-9937-96ff72dbc25b | Руководство по интеграции диспетчеризации | INDEXED | 1 | 2026-06-01T21:21:43.60661Z |
| CORP-RU-AV-016 | dfae45b9-e8f6-4f25-919f-8572ca1f894b | Политика багажных исключений | INDEXED | 1 | 2026-06-01T21:22:16.749541Z |

## Store Checks

| Store | Status | OK | Details |
|-------|--------|----|---------|
| Qdrant | passed | yes | `{"document_count": 16, "extra_document_ids": [], "missing_document_ids": [], "point_count": 16, "points_by_document_id": {"0f7c5f9f-4808-4d86-a8b9-29c3893d03c6": 1, "1b7d28c7-3a05-4501-826f-ba36b8e8aaf4": 1, "1c45b64f-5aaa-451c-b675-1079181ff069": 1, "1e07115f-b79a-4f2b-a2b2-88e3e7460fe6": 1, "22618bcb-ada0-497a-916c-e072110c70c5": 1, "337f4a65-efdc-4b3a-91a1-f2e3434439ca": 1, "33b3e4ed-755a-4646-8a68-3ea843e1fe24": 1, "43da091e-fcb9-4fde-8615-82518f4d452f": 1, "7b04026e-6663-4d40-b07a-6463b8afd19c": 1, "7b953631-a816-494e-acc6-ac539086b9b4": 1, "805c11c2-d915-4ca9-b188-b1116020e13e": 1, "82ae8890-6b63-4cff-9937-96ff72dbc25b": 1, "dfae45b9-e8f6-4f25-919f-8572ca1f894b": 1, "e30b55fe-d647-4563-99ce-d8820417f0c8": 1, "e6d8207a-460b-4f4f-a986-3dc143e51271": 1, "fa5c99e6-33d2-42ec-bb31-57630a765734": 1}}` |
| Neo4j | passed | yes | `{"entity_count_zero": [], "expected_count": 16, "extra": [], "java_entity_count_zero": [], "java_missing": [], "java_neo4j_count_mismatch": [], "java_status_not_indexed": [], "missing": [], "neo4j_count": 16, "ok": true}` |
