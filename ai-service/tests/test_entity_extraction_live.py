from __future__ import annotations

import os
from uuid import UUID

import pytest

from corp_rag_ai.pipeline.indexing.entity_extractor import EntityExtractionSource, GeminiEntityExtractor


@pytest.mark.integration
@pytest.mark.skipif("GEMINI_API_KEY" not in os.environ, reason="GEMINI_API_KEY is required for live Gemini extraction")
@pytest.mark.asyncio
async def test_live_gemini_extracts_expected_hr_policy_subset() -> None:
    extractor = GeminiEntityExtractor(api_key=os.environ["GEMINI_API_KEY"])
    result = await extractor.extract_parent(
        EntityExtractionSource(
            text=(
                "The HR Department owns the Remote Work Policy. "
                "Employees submit remote work requests in Workday."
            ),
            chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            parent_chunk_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            section_path=("Remote Work",),
        ),
        document_title="HR Remote Work Policy",
        language="en",
    )

    entity_keys = {(entity.normalized_name, entity.entity_type) for entity in result.entities}
    relation_types = {relation.relation_type for relation in result.relations}
    assert ("hr department", "department") in entity_keys
    assert ("remote work policy", "policy") in entity_keys
    assert "OWNS" in relation_types
