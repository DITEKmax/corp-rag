# Short Demo Video Checklist

## Status

Ready-to-record waiver recorded for Phase 8 Plan 08-04.

No video file is committed in this plan because short-video capture is a human
presentation artifact outside the current execution environment. The demo
materials are complete enough to record from [demo-script.md](demo-script.md)
without rerunning eval or changing corpus/model settings.

Next exact recording step:

```text
Record a 3-5 minute screen capture following docs/demo/demo-script.md, then add
the reviewed video artifact path here if it is intentionally committed.
```

## Recording setup

- Local compose stack is running from `infra/docker-compose.yml`.
- `docker compose --env-file infra/.env -f infra/docker-compose.yml ps` shows
  the demo services up.
- `http://localhost` opens the frontend.
- `http://localhost:3000` opens Langfuse.
- Admin credentials are read from ignored `infra/.env`.
- No secret values are shown on screen.
- Browser tabs prepared:
  - frontend chat
  - Langfuse traces
  - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
  - [08-KNOWN-LIMITATIONS.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md)

## Required scenes

1. Architecture boundary
   - Show frontend -> Java only.
   - State Java ownership: auth, documents, chat, audit, browser API.
   - State Python ownership: ingestion, retrieval, graph, guards, synthesis, eval.

2. Factual answer with citations
   - Ask: `Что требует регламент передачи рейса при передаче рейса между сменами?`
   - Show answer status and citation chips/source view.
   - Name `Регламент передачи рейса` as the primary citation source.

3. Langfuse latency breakdown
   - Open the live trace for the just-issued query.
   - Show guard, routing, retrieval, parent context, rerank, synthesis, output guard.
   - Point out that rerank is the dominant observed latency span.
   - Do not invent milliseconds; read them only if visible.

4. Injection/refusal
   - Show `ru-out-007` as blocked.
   - State `TIER_0_REGEX`, confidence `1.0`, outcome `refused_guard`.

5. Multi-hop limitation
   - Show `08-KNOWN-LIMITATIONS.md`.
   - Name waived rows: `ru-multihop-002/003/005/006`.
   - State that the current behavior is safe refusal, not fabricated synthesis.

6. Quality-vs-coverage close
   - Quality: `faithfulness=0.991`, `answer_relevancy=0.865`,
     `context_precision=1.0`, `context_recall=1.0`.
   - Coverage: `answered=16/30 answerable`, `outcome_accuracy=0.575`,
     `citation_doc_recall=0.533`.

## Review criteria

- The video does not claim production deployment readiness.
- The video does not hide the multi-hop waiver or router false-`MULTI_HOP`
  limitation.
- The video does not show secrets from `infra/.env`.
- The video shows at least one citation-backed factual answer.
- The video shows one live Langfuse trace.
- The video shows one injection/refusal or safe refusal scene.
- The video frames limited coverage as measured future work, not as a passed
  threshold.
