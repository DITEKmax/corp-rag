from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from corp_rag_ai.domain.document import ParsedDocument
from corp_rag_ai.domain.exceptions import INVALID_FILE_FORMAT, IndexingStage, stage_failure
from corp_rag_ai.pipeline.ingestion.parsers.markdown import MarkdownDocumentParser


class DoclingDocumentParser:
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
        try:
            markdown = await asyncio.to_thread(self._convert_to_markdown, content, mime_type)
        except Exception as exc:
            raise stage_failure(
                stage=IndexingStage.PARSING,
                error_code=INVALID_FILE_FORMAT,
                retryable=False,
                parser="docling",
                mime_type=mime_type,
                exception_class=exc,
            ) from exc

        if not markdown.strip():
            raise stage_failure(
                stage=IndexingStage.PARSING,
                error_code=INVALID_FILE_FORMAT,
                retryable=False,
                parser="docling",
                mime_type=mime_type,
            )

        parsed = await self._markdown_parser.parse(
            document_id=document_id,
            content=markdown.encode("utf-8"),
            mime_type="text/markdown",
            language=language,
        )
        warnings = list(parsed.parse_warnings)
        warnings.append("docling markdown export used; page metadata is not retained in this adapter")
        return parsed.model_copy(update={"parse_warnings": warnings})

    def _convert_to_markdown(self, content: bytes, mime_type: str) -> str:
        from docling.document_converter import DocumentConverter

        suffix = _suffix_for_mime_type(mime_type)
        with TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / f"document{suffix}"
            source_path.write_bytes(content)
            result = DocumentConverter().convert(source_path, raises_on_error=True)
            return result.document.export_to_markdown()


def _suffix_for_mime_type(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return ".pdf"
    return ".docx"
