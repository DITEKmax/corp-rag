from __future__ import annotations

from corp_rag_ai.pipeline.ingestion.sentence_boundary import (
    HARD_CUT_WARNING,
    count_tokens,
    find_sentence_boundaries,
    split_text_into_child_segments,
)


def test_splitter_is_deterministic_and_respects_hard_max() -> None:
    text = (
        "First paragraph has enough words to form a stable child chunk. "
        "Second sentence keeps the paragraph boundary useful.\n\n"
        "Second paragraph has another sentence for the next chunk. "
        "Final sentence closes the golden fixture."
    )

    first = split_text_into_child_segments(text, target_tokens=12, max_tokens=20, overlap_tokens=4)
    second = split_text_into_child_segments(text, target_tokens=12, max_tokens=20, overlap_tokens=4)

    assert first == second
    assert [segment.content for segment in first]
    assert all(segment.token_count <= 20 for segment in first)


def test_sentence_boundaries_skip_english_and_russian_abbreviations() -> None:
    text = (
        "Dr. Smith met the U.S. office. "
        "\u041f\u0440\u0438\u043c\u0435\u0440 \u0442.\u0435. "
        "\u0441 \u0441\u043e\u043a\u0440\u0430\u0449\u0435\u043d\u0438\u0435\u043c. Done."
    )
    boundaries = find_sentence_boundaries(text)

    assert text.index("Dr.") + len("Dr.") not in boundaries
    assert text.index("U.S.") + len("U.S.") not in boundaries
    assert text.index("\u0442.") + len("\u0442.") not in boundaries
    assert text.index("\u0442.\u0435.") + len("\u0442.\u0435.") not in boundaries
    assert text.index("office.") + len("office.") in boundaries
    assert text.index("Done.") + len("Done.") in boundaries


def test_overlap_starts_fresh_for_each_parent_split() -> None:
    parent_one = " ".join(f"alpha{i}" for i in range(80))
    parent_two = " ".join(f"beta{i}" for i in range(80))

    one_segments = split_text_into_child_segments(parent_one, target_tokens=10, max_tokens=14, overlap_tokens=3)
    two_segments = split_text_into_child_segments(parent_two, target_tokens=10, max_tokens=14, overlap_tokens=3)

    assert one_segments[0].start_token == 0
    assert two_segments[0].start_token == 0
    assert one_segments[1].start_token < one_segments[0].end_token
    assert two_segments[1].start_token < two_segments[0].end_token


def test_hard_cut_is_reported_when_no_boundary_exists() -> None:
    text = "x" * 5000

    segments = split_text_into_child_segments(text, target_tokens=5, max_tokens=8, overlap_tokens=0)

    assert count_tokens(text) > 8
    assert HARD_CUT_WARNING in segments[0].warnings
