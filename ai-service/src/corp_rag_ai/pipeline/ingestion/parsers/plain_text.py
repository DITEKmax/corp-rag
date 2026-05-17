from __future__ import annotations

from uuid import UUID

from corp_rag_ai.domain.document import ParsedBlockDraft, ParsedDocument, normalize_parsed_blocks
from corp_rag_ai.pipeline.ingestion.parsers.failures import invalid_file_format


class PlainTextDocumentParser:
    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument:
        text = " ".join(content.decode("utf-8", errors="replace").split())
        if not text:
            raise invalid_file_format(parser="plain_text", mime_type=mime_type)
        return normalize_parsed_blocks(
            document_id=document_id,
            language=language,
            blocks=[ParsedBlockDraft(type="paragraph", text=text)],
        )
