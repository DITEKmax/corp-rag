from __future__ import annotations

from uuid import uuid4

import pytest

from corp_rag_ai.domain.document import ParsedBlock, ParsedBlockDraft, normalize_parsed_blocks
from corp_rag_ai.domain.exceptions import UNSUPPORTED_FILE_TYPE, IndexingStage, StageFailure
from corp_rag_ai.pipeline.ingestion.parsers.base import MimeTypeParserDispatcher


def test_normalization_assigns_positions_and_nested_section_paths() -> None:
    document = normalize_parsed_blocks(
        document_id=uuid4(),
        language="ru",
        blocks=[
            ParsedBlockDraft(type="heading", text="Policy", level=1),
            ParsedBlockDraft(type="paragraph", text="Intro"),
            ParsedBlockDraft(type="heading", text="Scope", level=2),
            ParsedBlockDraft(type="list_item", text="Employees"),
            ParsedBlockDraft(type="heading", text="Appendix", level=1),
            ParsedBlockDraft(type="paragraph", text="Details"),
        ],
    )

    assert [block.position for block in document.blocks] == [0, 1, 2, 3, 4, 5]
    assert document.blocks[1].section_path == ["Policy"]
    assert document.blocks[3].section_path == ["Policy", "Scope"]
    assert document.blocks[5].section_path == ["Appendix"]


def test_parsed_block_has_only_locked_fields() -> None:
    assert set(ParsedBlock.model_fields) == {
        "type",
        "text",
        "level",
        "position",
        "page",
        "section_path",
    }


@pytest.mark.asyncio
async def test_dispatcher_maps_unsupported_mime_to_stage_failure() -> None:
    dispatcher = MimeTypeParserDispatcher({})

    with pytest.raises(StageFailure) as failure_info:
        await dispatcher.parse(
            document_id=uuid4(),
            content=b"data",
            mime_type="application/octet-stream",
            language="ru",
        )

    failure = failure_info.value
    assert failure.stage == IndexingStage.PARSING
    assert failure.error_code == UNSUPPORTED_FILE_TYPE
    assert failure.retryable is False
