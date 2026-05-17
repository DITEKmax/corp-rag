from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ParsedBlockType = Literal["heading", "paragraph", "list_item", "table", "preformatted"]


class ParsedBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: ParsedBlockType
    text: str
    level: int | None = None
    position: int
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped

    @field_validator("position")
    @classmethod
    def _position_must_be_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("position must be non-negative")
        return value

    @field_validator("page")
    @classmethod
    def _page_must_be_positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("page must be positive when present")
        return value

    @model_validator(mode="after")
    def _level_matches_block_type(self) -> ParsedBlock:
        if self.type == "heading":
            if self.level is None or not 1 <= self.level <= 6:
                raise ValueError("heading blocks require level 1..6")
        elif self.level is not None:
            raise ValueError("only heading blocks may set level")
        return self


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    language: str
    blocks: list[ParsedBlock]
    parse_warnings: list[str] = Field(default_factory=list)

    @field_validator("language")
    @classmethod
    def _language_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("language must not be blank")
        return stripped

    @field_validator("blocks")
    @classmethod
    def _blocks_must_not_be_empty(cls, value: list[ParsedBlock]) -> list[ParsedBlock]:
        if not value:
            raise ValueError("blocks must not be empty")
        return value


@dataclass(frozen=True, slots=True)
class ParsedBlockDraft:
    type: ParsedBlockType
    text: str
    level: int | None = None
    page: int | None = None


def normalize_parsed_blocks(
    *,
    document_id: UUID,
    language: str,
    blocks: list[ParsedBlockDraft],
    parse_warnings: list[str] | None = None,
) -> ParsedDocument:
    section_path: list[str] = []
    normalized: list[ParsedBlock] = []

    for position, block in enumerate(blocks):
        text = block.text.strip()
        if block.type == "heading":
            if block.level is None or not 1 <= block.level <= 6:
                raise ValueError("heading drafts require level 1..6")
            section_path = section_path[: block.level - 1]
            section_path.append(text)
            block_section_path = list(section_path)
        else:
            block_section_path = list(section_path)

        normalized.append(
            ParsedBlock(
                type=block.type,
                text=text,
                level=block.level,
                position=position,
                page=block.page,
                section_path=block_section_path,
            )
        )

    return ParsedDocument(
        document_id=document_id,
        language=language,
        blocks=normalized,
        parse_warnings=list(parse_warnings or []),
    )
