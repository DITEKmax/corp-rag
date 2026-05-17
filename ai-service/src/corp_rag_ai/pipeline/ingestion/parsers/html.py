from __future__ import annotations

from uuid import UUID

import trafilatura

from corp_rag_ai.domain.document import ParsedDocument
from corp_rag_ai.pipeline.ingestion.parsers.failures import invalid_file_format
from corp_rag_ai.pipeline.ingestion.parsers.markdown import MarkdownDocumentParser


class HtmlDocumentParser:
    def __init__(self, markdown_parser: MarkdownDocumentParser | None = None) -> None:
        self._markdown_parser = markdown_parser or MarkdownDocumentParser()

    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument:
        html = content.decode("utf-8", errors="replace")
        extracted = trafilatura.extract(
            html,
            output_format="markdown",
            include_comments=False,
            include_formatting=True,
            include_tables=True,
            favor_precision=True,
        )
        if not extracted or not extracted.strip():
            raise invalid_file_format(parser="trafilatura", mime_type=mime_type)
        return await self._markdown_parser.parse(
            document_id=document_id,
            content=extracted.encode("utf-8"),
            mime_type="text/markdown",
            language=language,
        )
