# Phase 04: User Setup Required

**Generated:** 2026-05-17
**Phase:** 04-python-ingestion-indexing
**Status:** Incomplete

Complete these items for live Gemini entity-extraction smoke tests and Phase 04 UAT. Unit tests mock Gemini and do not require this setup.

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `GEMINI_API_KEY` | Google AI Studio -> API keys | local shell environment for `ai-service` live tests and UAT |

## Account Setup

- [ ] **Google AI Studio access**
  - URL: https://aistudio.google.com/app/apikey
  - Skip if: You already have a Gemini API key with Gemini 2.0 Flash access.

## Verification

After setting the variable, verify with:

```powershell
cd ai-service
$env:GEMINI_API_KEY = "your-google-ai-studio-key"
uv run pytest tests/test_entity_extraction_live.py -m integration
```

Expected results:
- The live integration test runs instead of skipping.
- The test extracts the expected HR policy entity/relation subset.

---

**Once all items complete:** Mark status as "Complete" at top of file.
