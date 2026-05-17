from __future__ import annotations

from uuid import UUID

from markdown_it import MarkdownIt
from markdown_it.token import Token

from corp_rag_ai.domain.document import ParsedBlockDraft, ParsedDocument, normalize_parsed_blocks
from corp_rag_ai.pipeline.ingestion.parsers.failures import invalid_file_format


class MarkdownDocumentParser:
    def __init__(self) -> None:
        self._markdown = MarkdownIt("commonmark", {"html": False}).enable("table")

    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        drafts = self.parse_text(text)
        if not drafts:
            raise invalid_file_format(parser="markdown", mime_type=mime_type)
        return normalize_parsed_blocks(document_id=document_id, language=language, blocks=drafts)

    def parse_text(self, text: str) -> list[ParsedBlockDraft]:
        tokens = self._markdown.parse(text)
        drafts: list[ParsedBlockDraft] = []
        index = 0

        while index < len(tokens):
            token = tokens[index]
            if token.type == "heading_open":
                level = int(token.tag.removeprefix("h"))
                inline = _next_inline_content(tokens, index)
                if inline:
                    drafts.append(ParsedBlockDraft(type="heading", text=inline, level=level))
                index = _skip_until(tokens, index + 1, "heading_close")
            elif token.type == "paragraph_open":
                inline = _collect_until_close(tokens, index + 1, "paragraph_close")
                if inline:
                    drafts.append(ParsedBlockDraft(type="paragraph", text=inline))
                index = _skip_until(tokens, index + 1, "paragraph_close")
            elif token.type == "list_item_open":
                item_text = _collect_list_item_text(tokens, index)
                if item_text:
                    drafts.append(ParsedBlockDraft(type="list_item", text=item_text))
                index = _skip_balanced(tokens, index, "list_item_open", "list_item_close")
            elif token.type in {"fence", "code_block"}:
                if token.content.strip():
                    drafts.append(ParsedBlockDraft(type="preformatted", text=token.content.strip()))
                index += 1
            elif token.type == "table_open":
                table_text = _serialize_table(tokens, index)
                if table_text:
                    drafts.append(ParsedBlockDraft(type="table", text=table_text))
                index = _skip_until(tokens, index + 1, "table_close")
            else:
                index += 1

        return drafts


def _next_inline_content(tokens: list[Token], index: int) -> str:
    if index + 1 >= len(tokens) or tokens[index + 1].type != "inline":
        return ""
    return _clean_inline(tokens[index + 1].content)


def _collect_until_close(tokens: list[Token], index: int, close_type: str) -> str:
    parts: list[str] = []
    while index < len(tokens) and tokens[index].type != close_type:
        if tokens[index].type == "inline":
            content = _clean_inline(tokens[index].content)
            if content:
                parts.append(content)
        index += 1
    return " ".join(parts).strip()


def _collect_list_item_text(tokens: list[Token], index: int) -> str:
    parts: list[str] = []
    index += 1
    depth = 1
    while index < len(tokens) and depth:
        token = tokens[index]
        if token.type == "list_item_open":
            depth += 1
        elif token.type == "list_item_close":
            depth -= 1
        elif depth == 1 and token.type == "inline":
            content = _clean_inline(token.content)
            if content:
                parts.append(content)
        index += 1
    return " ".join(parts).strip()


def _serialize_table(tokens: list[Token], index: int) -> str:
    rows: list[list[str]] = []
    row: list[str] | None = None
    index += 1

    while index < len(tokens) and tokens[index].type != "table_close":
        token = tokens[index]
        if token.type == "tr_open":
            row = []
        elif token.type == "tr_close":
            if row:
                rows.append(row)
            row = None
        elif token.type == "inline" and row is not None:
            row.append(_clean_table_cell(token.content))
        index += 1

    if not rows:
        return ""

    width = max(len(row) for row in rows)
    padded_rows = [row + [""] * (width - len(row)) for row in rows]
    header = padded_rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in padded_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _skip_until(tokens: list[Token], index: int, close_type: str) -> int:
    while index < len(tokens) and tokens[index].type != close_type:
        index += 1
    return min(index + 1, len(tokens))


def _skip_balanced(tokens: list[Token], index: int, open_type: str, close_type: str) -> int:
    depth = 0
    while index < len(tokens):
        if tokens[index].type == open_type:
            depth += 1
        elif tokens[index].type == close_type:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(tokens)


def _clean_inline(value: str) -> str:
    return " ".join(value.split())


def _clean_table_cell(value: str) -> str:
    return _clean_inline(value).replace("|", "\\|")
