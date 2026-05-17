from __future__ import annotations

from uuid import uuid4

import pytest

from corp_rag_ai.domain.exceptions import INVALID_FILE_FORMAT, IndexingStage, StageFailure
from corp_rag_ai.pipeline.ingestion.parsers.docling_parser import DoclingDocumentParser


class _StubDoclingParser(DoclingDocumentParser):
    def __init__(self, markdown: str | Exception) -> None:
        super().__init__()
        self._markdown = markdown

    def _convert_to_markdown(self, content: bytes, mime_type: str) -> str:
        if isinstance(self._markdown, Exception):
            raise self._markdown
        return self._markdown


@pytest.mark.asyncio
async def test_docling_parser_uses_markdown_normalizer_and_records_page_tradeoff() -> None:
    parser = _StubDoclingParser("# Contract\n\nBody")
    document = await parser.parse(
        document_id=uuid4(),
        content=b"%PDF",
        mime_type="application/pdf",
        language="en",
    )

    assert [block.type for block in document.blocks] == ["heading", "paragraph"]
    assert document.blocks[1].section_path == ["Contract"]
    assert document.parse_warnings == [
        "docling markdown export used; page metadata is not retained in this adapter"
    ]


@pytest.mark.asyncio
async def test_docling_parser_maps_conversion_errors_to_sanitized_stage_failure() -> None:
    parser = _StubDoclingParser(RuntimeError("secret source text"))

    with pytest.raises(StageFailure) as failure_info:
        await parser.parse(
            document_id=uuid4(),
            content=b"broken",
            mime_type="application/pdf",
            language="en",
        )

    failure = failure_info.value
    assert failure.stage == IndexingStage.PARSING
    assert failure.error_code == INVALID_FILE_FORMAT
    assert "secret source text" not in failure.to_error_message()
