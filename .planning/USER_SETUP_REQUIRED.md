# User Setup Required

## Phase 04 LLM Provider

Set `OPENROUTER_API_KEY` before live DeepSeek/OpenRouter tests and Phase 04 UAT.

- Key URL: https://openrouter.ai/keys
- Model ID: `deepseek/deepseek-v4-flash:free`
- Base URL: `https://openrouter.ai/api/v1`

PowerShell smoke:

```powershell
cd ai-service
$env:OPENROUTER_API_KEY = "your-openrouter-key"
uv run pytest tests/test_deepseek_extraction_live.py -m integration
```
