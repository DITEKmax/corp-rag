# Russian Retrieval Ablation

| Field | Value |
|---|---|
| Corpus version | `ru-aviation-logistics-v1` |
| Corpus hash | `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984` |
| Eval timestamp | `2026-06-01T17:52:44.365244+00:00` |
| External judge used | `false` |
| Qdrant collection | `documents_chunks` |
| Qdrant point count | `16` |
| Source route report | `C:\Users\maksd\IntelliJIDEA\corp-rag\ai-service\eval\reports\ragas_ru.json` |
| Dense/sparse payload smoke | `passed; dense_hits=1; sparse_hits=1; sample_documentId=e077eb72-0e27-4e1e-9b63-34316e88b546` |

## Vector Scope

Included vector ids (15): `ru-factual-001, ru-factual-002, ru-factual-003, ru-factual-005, ru-factual-006, ru-factual-007, ru-factual-008, ru-aggregation-004, ru-aggregation-006, ru-aggregation-009, ru-aggregation-010, ru-multihop-007, ru-multihop-008, ru-multihop-009, ru-multihop-010`

Graph-route ids (14): `ru-factual-004, ru-factual-010, ru-aggregation-001, ru-aggregation-002, ru-aggregation-003, ru-aggregation-005, ru-aggregation-007, ru-aggregation-008, ru-multihop-001, ru-multihop-002, ru-multihop-003, ru-multihop-004, ru-multihop-005, ru-multihop-006`

Excluded ids:

| ID | Reason | Route |
|---|---|---|
| `ru-factual-009` | non_retrieval_route | UNSUPPORTED |
| `ru-out-001` | no_expected_doc_ids | FACTUAL |
| `ru-out-002` | no_expected_doc_ids | FACTUAL |
| `ru-out-003` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-004` | no_expected_doc_ids | FACTUAL |
| `ru-out-005` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-006` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-007` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-008` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-009` | no_expected_doc_ids | UNSUPPORTED |
| `ru-out-010` | no_expected_doc_ids | UNSUPPORTED |

Route discrepancies:

| ID | Golden type | Actual route | Retrieval family |
|---|---|---|---|
| `ru-factual-004` | factual | MULTI_HOP | graph |
| `ru-factual-009` | factual | UNSUPPORTED | excluded |
| `ru-factual-010` | factual | AGGREGATION | graph |
| `ru-aggregation-004` | aggregation | FACTUAL | vector |
| `ru-aggregation-006` | aggregation | FACTUAL | vector |
| `ru-aggregation-009` | aggregation | COMPARISON | vector |
| `ru-aggregation-010` | aggregation | FACTUAL | vector |
| `ru-multihop-007` | multi_hop | FACTUAL | vector |
| `ru-multihop-008` | multi_hop | FACTUAL | vector |
| `ru-multihop-009` | multi_hop | FACTUAL | vector |
| `ru-multihop-010` | multi_hop | FACTUAL | vector |

## Vector Metrics

| Mode | Records | recall@5 | recall@10 | MRR | Notes |
|---|---:|---:|---:|---:|---|
| `bm25` | 15 | 0.8778 | 0.9667 | 0.9111 |  |
| `dense` | 15 | 0.9556 | 1.0000 | 0.9667 |  |
| `sparse` | 15 | 0.9778 | 1.0000 | 1.0000 |  |
| `hybrid` | 15 | 0.9778 | 1.0000 | 1.0000 |  |
| `hybrid+reranker` | 15 | 0.9778 | 1.0000 | 1.0000 |  |

## Interpretation

- BM25 (0.88/0.97/0.91) is visibly weaker than learned retrieval modes, supporting the thesis: bge-m3 learned sparse превосходит классический BM25.
- Sparse, hybrid, and hybrid+reranker all hit the ceiling at recall@10=1.0/1.0/1.0 and MRR=1.0/1.0/1.0.
- The reranker adds no measurable lift here because retrieval saturates on a small corpus (16 indexed docs, 15 vector-routed questions): relevant documents are already in top-5 with ideal MRR. This is a scale limitation of the experiment, not evidence that reranking is useless; reranker value should appear on larger corpora with noisier candidate sets.
- The graph route remains a separate section with recall@10=0.29, consistent with the known Phase 8 multi-hop debt.
- `ru-factual-009` is another false-UNSUPPORTED case: the router marked an answerable factual question as UNSUPPORTED, the same Phase 8 router debt seen in the 7.1 multi-hop findings.

## Graph Route

Graph-routed records are reported separately because graph retrieval is not comparable to BM25/dense/sparse/hybrid vector modes.

| Metric | Value |
|---|---:|
| record_count | 14 |
| citeable_evidence_rate | 0.2857 |
| no_evidence_refusal_count | 10 |
| guard_refusal_count | 0 |
| recall@5 | 0.2857 |
| recall@10 | 0.2857 |
| mrr | 0.2857 |

| ID | Route | Outcome | Citeable Evidence | recall@5 | recall@10 | MRR | Warnings |
|---|---|---|---|---:|---:|---:|---|
| `ru-factual-004` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-factual-010` | AGGREGATION | answered | true | 1.0000 | 1.0000 | 1.0000 |  |
| `ru-aggregation-001` | AGGREGATION | answered | true | 1.0000 | 1.0000 | 1.0000 |  |
| `ru-aggregation-002` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-aggregation-003` | AGGREGATION | answered | true | 1.0000 | 1.0000 | 1.0000 |  |
| `ru-aggregation-005` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-aggregation-007` | AGGREGATION | answered | true | 1.0000 | 1.0000 | 1.0000 |  |
| `ru-aggregation-008` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-001` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-002` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-003` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-004` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-005` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |
| `ru-multihop-006` | MULTI_HOP | refused_no_evidence | false | 0.0000 | 0.0000 | 0.0000 |  |

## Runner Notes

- This is retrieval-only; RAGAS judge calls were not invoked for ablation variants.
- `bm25` is classical lexical eval-only retrieval over the frozen corpus.
- `sparse` is learned bge-m3 sparse retrieval through Qdrant, distinct from BM25.
- `hybrid+reranker` reranks the same hybrid retrieval top-k candidate layer used for the `hybrid` mode.
