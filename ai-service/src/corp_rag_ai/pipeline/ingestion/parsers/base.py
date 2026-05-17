from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from corp_rag_ai.domain.document import ParsedDocument
from corp_rag_ai.domain.exceptions import (
    IndexingStage,
    StageFailure,
    UNSUPPORTED_FILE_TYPE,
    stage_failure,
)


class DocumentParser(Protocol):
    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument: ...


class MimeTypeParserDispatcher:
    def __init__(self, parsers: Mapping[str, DocumentParser]) -> None:
        self._parsers = {_normalize_mime_type(key): parser for key, parser in parsers.items()}

    @property
    def supported_mime_types(self) -> frozenset[str]:
        return frozenset(self._parsers)

    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument:
        normalized_mime_type = _normalize_mime_type(mime_type)
        parser = self._parsers.get(normalized_mime_type)
        if parser is None:
            raise _unsupported_mime_type(normalized_mime_type)
        return await parser.parse(
            document_id=document_id,
            content=content,
            mime_type=normalized_mime_type,
            language=language,
        )


def build_default_parser_dispatcher() -> MimeTypeParserDispatcher:
    from corp_rag_ai.pipeline.ingestion.parsers.docling_parser import DoclingDocumentParser
    from corp_rag_ai.pipeline.ingestion.parsers.html import HtmlDocumentParser
    from corp_rag_ai.pipeline.ingestion.parsers.markdown import MarkdownDocumentParser
    from corp_rag_ai.pipeline.ingestion.parsers.plain_text import PlainTextDocumentParser

    markdown_parser = MarkdownDocumentParser()
    html_parser = HtmlDocumentParser(markdown_parser)
    docling_parser = DoclingDocumentParser(markdown_parser)
    plain_text_parser = PlainTextDocumentParser()

    return MimeTypeParserDispatcher(
        {
            "application/pdf": docling_parser,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": docling_parser,
            "text/html": html_parser,
            "application/xhtml+xml": html_parser,
            "text/markdown": markdown_parser,
            "text/x-markdown": markdown_parser,
            "text/plain": plain_text_parser,
        }
    )


def _normalize_mime_type(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def _unsupported_mime_type(mime_type: str) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.PARSING,
        error_code=UNSUPPORTED_FILE_TYPE,
        retryable=False,
        parser="dispatcher",
        mime_type=mime_type or "unknown",
    )
