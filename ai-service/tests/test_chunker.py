from __future__ import annotations

from uuid import UUID, uuid5

from corp_rag_ai.domain.document import ParsedBlock, ParsedBlockDraft, ParsedDocument, normalize_parsed_blocks
from corp_rag_ai.pipeline.ingestion.chunker import DocumentChunker, OVERSIZED_TABLE_WARNING


def test_chunker_produces_deterministic_parent_and_child_ids_and_texts() -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    document = normalize_parsed_blocks(
        document_id=document_id,
        language="en",
        blocks=[
            ParsedBlockDraft(type="heading", text="Policy", level=1),
            ParsedBlockDraft(
                type="paragraph",
                text=(
                    "Employees may request vacation through the HR portal. "
                    "Managers review requests within two business days. "
                    "Approved vacation is visible in the schedule."
                ),
            ),
            ParsedBlockDraft(type="heading", text="Scope", level=2),
            ParsedBlockDraft(type="list_item", text="Full-time employees"),
            ParsedBlockDraft(type="list_item", text="Part-time employees"),
        ],
    )
    chunker = DocumentChunker(
        parent_target_tokens=80,
        parent_max_tokens=120,
        child_target_tokens=8,
        child_max_tokens=18,
        child_overlap_tokens=2,
    )

    first = chunker.chunk(document, document_title="HR Policy")
    second = chunker.chunk(document, document_title="HR Policy")

    assert first == second
    assert first.parents[0].parent_chunk_id == uuid5(document_id, "parent:0")
    assert first.children[0].chunk_id == uuid5(first.parents[0].parent_chunk_id, "child:0")
    assert first.children[0].content_for_embedding.startswith("HR Policy \u203a Policy\n\n")
    assert "HR Policy \u203a" not in first.children[0].content


def test_chunker_keeps_parent_local_and_global_child_positions_separate() -> None:
    document_id = UUID("22222222-2222-2222-2222-222222222222")
    document = ParsedDocument(
        document_id=document_id,
        language="en",
        blocks=[
            ParsedBlock(
                type="paragraph",
                text=" ".join(f"alpha{i}" for i in range(70)),
                position=0,
                section_path=["Alpha"],
            ),
            ParsedBlock(
                type="paragraph",
                text=" ".join(f"beta{i}" for i in range(70)),
                position=1,
                section_path=["Beta"],
            ),
        ],
    )
    chunker = DocumentChunker(
        parent_target_tokens=200,
        parent_max_tokens=240,
        child_target_tokens=10,
        child_max_tokens=14,
        child_overlap_tokens=3,
    )

    result = chunker.chunk(document, document_title="Ops Handbook")
    beta_children = [child for child in result.children if child.section_path == ("Beta",)]

    assert len(result.parents) == 2
    assert beta_children[0].position_in_parent == 0
    assert beta_children[0].position > 0
    assert beta_children[0].chunk_id == uuid5(result.parents[1].parent_chunk_id, "child:0")


def test_table_block_is_atomic_even_when_oversized() -> None:
    document_id = UUID("33333333-3333-3333-3333-333333333333")
    table = "| A | B |\n| --- | --- |\n" + "\n".join(f"| row{i} | {'word ' * 20}|" for i in range(8))
    document = ParsedDocument(
        document_id=document_id,
        language="en",
        blocks=[ParsedBlock(type="table", text=table, position=0, section_path=["Appendix"])],
    )
    chunker = DocumentChunker(
        parent_target_tokens=30,
        parent_max_tokens=40,
        child_target_tokens=8,
        child_max_tokens=10,
        child_overlap_tokens=2,
    )

    result = chunker.chunk(document, document_title="Table Doc")

    assert len(result.parents) == 1
    assert len(result.children) == 1
    assert result.children[0].content == table
    assert OVERSIZED_TABLE_WARNING in result.parents[0].warnings
    assert result.parent_records()[0].content == table


def test_child_payload_candidate_uses_locked_qdrant_shape_without_embedding_text() -> None:
    document_id = UUID("44444444-4444-4444-4444-444444444444")
    document = ParsedDocument(
        document_id=document_id,
        language="ru",
        blocks=[ParsedBlock(type="paragraph", text="Policy body", position=0, page=3, section_path=["HR"])],
    )
    child = DocumentChunker().chunk(document, document_title="HR Policy").children[0]

    payload = child.to_qdrant_payload(
        document_title="HR Policy",
        language="ru",
        doc_type="POLICY",
        department="HR",
        access_level="INTERNAL",
        is_sanitized=False,
        sanitizer_flags=("PROMPT_IGNORE_INSTRUCTIONS",),
    )

    assert payload["sectionPath"] == ["HR"]
    assert payload["position"] == 0
    assert payload["page"] == 3
    assert payload["content"] == "Policy body"
    assert payload["isSanitized"] is False
    assert payload["sanitizerFlags"] == ["PROMPT_IGNORE_INSTRUCTIONS"]
    assert "content_for_embedding" not in payload
