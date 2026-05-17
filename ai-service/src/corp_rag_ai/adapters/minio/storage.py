from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from corp_rag_ai.domain.exceptions import DEPENDENCY_UNAVAILABLE, IndexingStage, StageFailure, stage_failure


@dataclass(frozen=True, slots=True)
class MinioObjectRef:
    bucket: str
    key: str

    def __post_init__(self) -> None:
        if not self.bucket.strip():
            raise ValueError("bucket must not be blank")
        if not self.key.strip():
            raise ValueError("key must not be blank")


@dataclass(frozen=True, slots=True)
class FetchedObject:
    body: bytes
    object_ref: MinioObjectRef


class MinioObjectNotFound(Exception):
    """Raised when Java published an object reference that MinIO no longer has."""


class MinioDocumentStore:
    def __init__(self, client: Any, *, fetch_timeout_seconds: float = 30.0) -> None:
        if fetch_timeout_seconds <= 0:
            raise ValueError("fetch_timeout_seconds must be positive")
        self._client = client
        self._fetch_timeout_seconds = fetch_timeout_seconds

    @classmethod
    def from_settings(
        cls,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        fetch_timeout_seconds: float = 30.0,
    ) -> MinioDocumentStore:
        from minio import Minio

        return cls(
            Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            ),
            fetch_timeout_seconds=fetch_timeout_seconds,
        )

    async def fetch(self, object_ref: MinioObjectRef) -> FetchedObject:
        try:
            body = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_blocking, object_ref),
                timeout=self._fetch_timeout_seconds,
            )
        except TimeoutError as exc:
            raise _dependency_failure(exc, retryable=True, detail="timeout") from exc
        except MinioObjectNotFound:
            raise
        except StageFailure:
            raise
        except Exception as exc:
            raise _classify_minio_failure(exc) from exc
        return FetchedObject(body=body, object_ref=object_ref)

    def _fetch_blocking(self, object_ref: MinioObjectRef) -> bytes:
        response = self._client.get_object(object_ref.bucket, object_ref.key)
        try:
            return bytes(response.read())
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
            release_conn = getattr(response, "release_conn", None)
            if release_conn is not None:
                release_conn()


def _classify_minio_failure(exc: Exception) -> Exception:
    status_code = _status_code(exc)
    error_code = str(getattr(exc, "code", "") or "")
    if status_code == 404 or error_code in {"NoSuchBucket", "NoSuchKey", "NoSuchObject"}:
        return MinioObjectNotFound(str(exc))
    if status_code == 403 or error_code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
        return _dependency_failure(exc, retryable=False, detail="status_403")
    if _looks_network_or_timeout(exc):
        return _dependency_failure(exc, retryable=True, detail=exc.__class__.__name__)
    return _dependency_failure(exc, retryable=True, detail=exc.__class__.__name__)


def _dependency_failure(exc: Exception, *, retryable: bool, detail: str) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.FETCHING,
        error_code=DEPENDENCY_UNAVAILABLE,
        retryable=retryable,
        detail=detail or exc.__class__.__name__,
    )


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status", None)
    if isinstance(response_status, int):
        return response_status
    response_status_code = getattr(response, "status_code", None)
    return response_status_code if isinstance(response_status_code, int) else None


def _looks_network_or_timeout(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    return "timeout" in name or "connection" in name or "network" in name or "http" in name
