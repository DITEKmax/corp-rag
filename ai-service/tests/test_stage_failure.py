from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from corp_rag_ai.domain.exceptions import (
    INDEXING_PIPELINE_ERROR,
    INVALID_FILE_FORMAT,
    IndexingStage,
    StageFailure,
    build_document_indexing_failed_payload,
    stage_failure,
)


def test_stage_failure_uses_exception_class_name_not_exception_text() -> None:
    exception = RuntimeError("secret document text and raw dependency body")

    failure = stage_failure(
        stage=IndexingStage.EMBEDDING,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        exception_class=exception,
    )
    message = failure.to_error_message()

    assert "Local FlagEmbedding bge-m3" in message
    assert "RuntimeError" in message
    assert "secret document text" not in message
    assert "raw dependency body" not in message


def test_stage_failure_missing_template_values_are_safe_placeholders() -> None:
    failure = stage_failure(
        stage=IndexingStage.PARSING,
        error_code=INVALID_FILE_FORMAT,
        retryable=False,
        mime_type="application/pdf",
    )

    assert "Parser n/a" in failure.to_error_message()


def test_stage_failure_limits_message_length() -> None:
    failure = StageFailure(
        stage=IndexingStage.VECTOR_UPSERT,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=True,
        message_template="{detail}",
        template_vars={"detail": "x" * 3000},
    )

    message = failure.to_error_message(max_len=64)

    assert len(message) <= 64
    assert message.endswith("...")


def test_stage_failure_redacts_traceback_template_values() -> None:
    failure = StageFailure(
        stage=IndexingStage.GRAPH_UPSERT,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        message_template="{detail}",
        template_vars={"detail": "Traceback (most recent call last):\nsecret stack"},
    )

    assert failure.to_error_message() == "traceback-redacted"


def test_failed_payload_matches_asyncapi_field_names_and_defaults_retry_count() -> None:
    document_id = uuid4()
    failed_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    failure = stage_failure(
        stage="PARSING",
        error_code=INVALID_FILE_FORMAT,
        retryable=False,
        parser="docling",
        mime_type="application/pdf",
    )

    payload = build_document_indexing_failed_payload(
        document_id=document_id,
        failure=failure,
        failed_at=failed_at,
    )

    assert set(payload) == {
        "documentId",
        "stage",
        "errorCode",
        "errorMessage",
        "failedAt",
        "retryable",
        "retryCount",
    }
    assert payload["documentId"] == str(document_id)
    assert payload["stage"] == "PARSING"
    assert payload["errorCode"] == "INVALID_FILE_FORMAT"
    assert payload["failedAt"] == "2026-05-17T12:00:00Z"
    assert payload["retryable"] is False
    assert payload["retryCount"] == 0
