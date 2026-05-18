# Phase 04: User Setup Required

**Generated:** 2026-05-17
**Phase:** 04-python-ingestion-indexing
**Status:** Incomplete

Complete these items for live DeepSeek/OpenRouter entity-extraction smoke tests and Phase 04 UAT. Unit tests mock OpenRouter responses and do not require this setup.

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `OPENROUTER_API_KEY` | OpenRouter -> API keys | local shell environment for `ai-service` live tests and `infra/.env` for UAT |
| [ ] | `OPENROUTER_BASE_URL` | fixed default `https://openrouter.ai/api/v1` | optional override only |
| [ ] | `DEEPSEEK_MODEL_ID` | fixed default `deepseek/deepseek-v4-flash:free` | optional override only for paid tier |

## Account Setup

- [ ] **OpenRouter API key**
  - URL: https://openrouter.ai/keys
  - Skip if: You already have an OpenRouter key with access to `deepseek/deepseek-v4-flash:free`.

## Verification

After setting the variable, verify with:

```powershell
cd ai-service
$env:OPENROUTER_API_KEY = "your-openrouter-key"
uv run pytest tests/test_deepseek_extraction_live.py -m integration
```

Expected results:
- The live integration test runs instead of skipping.
- The test extracts the expected HR policy entity/relation subset.

---

**Once all items complete:** Mark status as "Complete" at top of file.
