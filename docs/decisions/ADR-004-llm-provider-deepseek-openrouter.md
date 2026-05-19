# ADR-004: LLM provider decision - DeepSeek V4 Flash via OpenRouter

- **Status:** Accepted
- **Date:** 2026-05-18
- **Affected components:** Python AI Service, ingestion entity extraction, Phase 5 query router, guards, answer generation, synthesizer

## Context

The project needs one hosted LLM path that works for academic demo constraints, structured extraction, guarded routing, and answer generation. Phase 4 UAT P2 showed that the previous hosted Flash path is not available for this user/project setup because the provider returned policy-level quota `limit=0` for all relevant metrics. Keeping a fallback chain would add test surface without helping UAT, because the blocked provider cannot be used in the target environment.

## Decision

Use `deepseek/deepseek-v4-flash:free` through OpenRouter as the default single LLM provider/model ID for:

- entity and relation extraction during indexing;
- answer generation with citations;
- query router classification;
- input guard classifier;
- output guard and synthesizer flows;
- shared `llm_client` integration in Phase 5.

The Python service uses the OpenAI Python SDK with `base_url=https://openrouter.ai/api/v1` and `OPENROUTER_API_KEY`. Structured outputs use strict `json_schema` mode and the OpenRouter response-healing plugin for non-streaming JSON calls.

## Alternatives Considered

| Alternative | Outcome | Reason |
|---|---|---|
| Keep previous hosted Flash path | Rejected | Policy-level quota block in the target environment and billing/regional risk |
| Use an older Flash model from the same provider | Rejected | Same provider-policy risk and slower model path |
| Older DeepSeek OpenRouter model | Rejected for primary | Older, more expensive, and no 1M context; remains a known fallback option if needed |
| Claude/OpenAI direct | Rejected | Higher quality but no suitable free tier for the project constraints |
| Local LLM through Ollama/llama.cpp | Rejected | 16GB RAM is not enough for a serious local LLM plus local bge-m3 in the MVP stack |

## Consequences

Positive:

- One SDK, one API key, and one model ID simplify testing and operations.
- The LLM requirement is satisfied with an open-source model.
- OpenRouter reduces direct single-provider access risk.
- Strict schema output and response healing reduce malformed JSON failures before Pydantic validation.

Tradeoffs:

- OpenRouter remains an external dependency and can rate-limit free-tier usage.
- DeepSeek V4 Flash is newer, so live UAT must keep an explicit P2 smoke.
- Paid usage should be monitored if indexing large corpora creates hundreds of extraction calls.
- Free tier (`:free` suffix) selected for diploma scope. Rate limit 50 RPD without credit / 1000 RPD with $10 OpenRouter top-up. Trade-off: shared infrastructure latency variability vs $0 cost. Paid variant of same model available via `DEEPSEEK_MODEL_ID` override for production deployment.

## Implementation Notes

- Runtime env: `OPENROUTER_API_KEY`, optional `OPENROUTER_BASE_URL`, optional `DEEPSEEK_MODEL_ID`.
- Default model ID: `deepseek/deepseek-v4-flash:free`.
- Removed the previous provider SDK dependency.
- Added dependency: `openai>=1.40,<2.0`.
