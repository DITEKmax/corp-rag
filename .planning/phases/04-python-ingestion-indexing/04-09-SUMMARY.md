---
phase: "04-python-ingestion-indexing"
plan: "09"
subsystem: "llm-provider-pivot"
tags: [openrouter, deepseek, entity-extraction, uat-preflight]
status: complete
key-files:
  created:
    - ".planning/phases/04-python-ingestion-indexing/04-09-PLAN.md"
    - ".planning/phases/04-python-ingestion-indexing/04-09-SUMMARY.md"
    - ".planning/USER_SETUP_REQUIRED.md"
    - "ai-service/tests/test_deepseek_extraction_live.py"
    - "docs/ADR-001.md"
    - "docs/ADR-004.md"
    - "docs/decisions/ADR-004-llm-provider-deepseek-openrouter.md"
  modified:
    - "ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py"
    - "ai-service/src/corp_rag_ai/config.py"
    - "ai-service/src/corp_rag_ai/main.py"
    - "ai-service/src/corp_rag_ai/domain/exceptions.py"
    - "ai-service/pyproject.toml"
    - "ai-service/uv.lock"
    - "ai-service/tests"
    - "docs/ARCHITECTURE.md"
    - ".planning/phases/04-python-ingestion-indexing/04-CONTEXT.md"
    - ".planning/phases/04-python-ingestion-indexing/04-DISCUSSION-LOG.md"
    - ".planning/phases/04-python-ingestion-indexing/04-UAT.md"
    - ".env.example"
    - "infra/.env.example"
    - "infra/docker-compose.yml"
metrics:
  tests: "97 passed, 5 skipped"
  live_p2: "skipped locally because OPENROUTER_API_KEY is not set"
---

# Phase 04 Plan 09: LLM Provider Pivot Summary

## Objective

Pivot Phase 4 LLM usage from the blocked hosted Flash provider to `deepseek/deepseek-v4-flash` through OpenRouter, preserving structured entity extraction and unblocking UAT P2.

## Tasks

1. Replaced the provider SDK dependency with `openai>=1.40,<2.0` and refreshed `uv.lock`.
2. Rewrote entity extraction as `DeepSeekEntityExtractor` using `AsyncOpenAI`, OpenRouter `base_url`, strict `json_schema`, response-healing plugin, bounded dependency retry, one malformed-output retry, and sanitized Pydantic schema.
3. Updated settings and FastAPI wiring to use `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, and `DEEPSEEK_MODEL_ID`.
4. Reworked unit, fixture, live, and smoke tests around OpenAI-compatible chat completions.
5. Updated failure matrix, UAT, setup docs, env examples, architecture, and ADRs for the DeepSeek/OpenRouter decision.

## Commits

| Commit | Description |
|---|---|
| this atomic commit | `feat(phase4.5): pivot LLM provider Gemini -> DeepSeek V4 Flash via OpenRouter` |

## Verification

| Check | Result |
|---|---|
| `uv lock` | passed; removed previous provider SDK, added `openai 1.109.1` |
| `uv run pytest tests/test_entity_extractor.py tests/test_entity_extraction_fixture.py -q` | 10 passed |
| `uv run --with pyyaml --with pydantic python scripts/verify-contracts.py` with explicit `MAVEN_CMD` | passed |
| `uv run pytest tests -q` | 97 passed, 5 skipped |
| `uv run pytest tests/test_deepseek_extraction_live.py -m integration -q -s` | skipped locally; `OPENROUTER_API_KEY` not set |
| `rg -n "gemini\|google-genai\|GEMINI_API_KEY" ai-service/src ai-service/tests docs -S` | zero matches |
| `rg -n "google-genai" ai-service/uv.lock ai-service/pyproject.toml` | zero matches |
| `rg -n "deepseek-v4-flash" ai-service/src` | found config and extractor defaults |

## Deviations

- `python scripts/verify-contracts.py` could not run through the Windows Store `python.exe` shim in this shell. The same script passed through `uv run` with `pyyaml`, `pydantic`, and explicit `MAVEN_CMD`.
- The live DeepSeek/OpenRouter P2 test was not executed against the network because `OPENROUTER_API_KEY` is not set in this environment.

## Self-Check

PASSED. Runtime code/tests/docs no longer contain the old provider SDK/key names, default tests remain CI-safe, and UAT P2 now targets DeepSeek/OpenRouter.
