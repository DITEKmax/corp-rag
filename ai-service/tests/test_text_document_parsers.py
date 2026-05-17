from __future__ import annotations

from uuid import uuid4

import pytest

from corp_rag_ai.domain.exceptions import INVALID_FILE_FORMAT, StageFailure
from corp_rag_ai.pipeline.ingestion.parsers.html import HtmlDocumentParser
from corp_rag_ai.pipeline.ingestion.parsers.markdown import MarkdownDocumentParser
from corp_rag_ai.pipeline.ingestion.parsers.plain_text import PlainTextDocumentParser


@pytest.mark.asyncio
async def test_markdown_parser_preserves_headings_list_items_preformatted_and_tables() -> None:
    parser = MarkdownDocumentParser()
    document = await parser.parse(
        document_id=uuid4(),
        content=(
            b"# Policy\n\n"
            b"Intro paragraph.\n\n"
            b"## Scope\n\n"
            b"- First item\n"
            b"- Second item\n\n"
            b"```text\nkeep    spacing\n```\n\n"
            b"| A | B |\n|---|---|\n| 1 | 2 |\n"
        ),
        mime_type="text/markdown",
        language="en",
    )

    assert [block.type for block in document.blocks] == [
        "heading",
        "paragraph",
        "heading",
        "list_item",
        "list_item",
        "preformatted",
        "table",
    ]
    assert [block.level for block in document.blocks[:3]] == [1, None, 2]
    assert document.blocks[3].text == "First item"
    assert document.blocks[4].text == "Second item"
    assert document.blocks[6].text == "| A | B |\n| --- | --- |\n| 1 | 2 |"
    assert document.blocks[6].section_path == ["Policy", "Scope"]


@pytest.mark.asyncio
async def test_html_parser_extracts_main_content_without_boilerplate() -> None:
    parser = HtmlDocumentParser()
    document = await parser.parse(
        document_id=uuid4(),
        content=(
            b"<html><body><nav>Ignore navigation</nav>"
            b"<article><h1>Policy</h1><p>Main policy body.</p></article>"
            b"<footer>Ignore footer</footer></body></html>"
        ),
        mime_type="text/html",
        language="en",
    )

    combined_text = "\n".join(block.text for block in document.blocks)

    assert "Main policy body" in combined_text
    assert "Ignore navigation" not in combined_text
    assert "Ignore footer" not in combined_text


@pytest.mark.asyncio
async def test_plain_text_parser_returns_single_paragraph_and_rejects_empty_text() -> None:
    parser = PlainTextDocumentParser()
    document = await parser.parse(
        document_id=uuid4(),
        content=b" First line\n\nsecond line ",
        mime_type="text/plain",
        language="en",
    )

    assert len(document.blocks) == 1
    assert document.blocks[0].type == "paragraph"
    assert document.blocks[0].text == "First line second line"

    with pytest.raises(StageFailure) as failure_info:
        await parser.parse(document_id=uuid4(), content=b"  \n\t ", mime_type="text/plain", language="en")

    assert failure_info.value.error_code == INVALID_FILE_FORMAT
