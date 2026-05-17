from __future__ import annotations

from corp_rag_ai.domain.exceptions import (
    INVALID_FILE_FORMAT,
    IndexingStage,
    StageFailure,
    stage_failure,
)


def invalid_file_format(*, parser: str, mime_type: str) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.PARSING,
        error_code=INVALID_FILE_FORMAT,
        retryable=False,
        parser=parser,
        mime_type=mime_type,
    )
