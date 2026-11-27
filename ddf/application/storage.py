from typing import BinaryIO, Protocol

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ObjectMeta:
    size: int
    content_type: str
    last_modified: datetime
    checksum: str | None = None


@dataclass(frozen=True, slots=True)
class MultipartPart:
    part_number: int
    etag: str


@dataclass(frozen=True, slots=True)
class UploadedMultipartPart(MultipartPart):
    size_bytes: int


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class ObjectStorage(Protocol):
    async def upload(self, file: bytes | BinaryIO, storage_key: str, content_type: str) -> None: ...

    async def delete(self, storage_key: str) -> None: ...

    async def create_upload_url(
        self,
        storage_key: str,
        content_type: str,
        checksum: str | None = None,
        expires_in: int = 3600,
    ) -> str: ...

    async def create_download_url(self, storage_key: str, expires_in: int = 3600) -> str: ...

    async def get_metadata(self, storage_key: str) -> ObjectMeta: ...

    async def upload_stream(
        self,
        file_stream: AsyncReadable,
        storage_key: str,
        mime_type: str,
        chunk_size: int = 5 * 1024 * 1024,
    ) -> None: ...

    async def download_stream(
        self,
        storage_key: str,
        chunk_size: int = 5 * 1024 * 1024,
    ) -> AsyncIterator[bytes]: ...


class MultipartStorage(Protocol):
    async def create_multipart_upload(self, storage_key: str, content_type: str) -> str: ...

    async def create_upload_part_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
        expires_in: int = 3600,
    ) -> str: ...

    async def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: Sequence[MultipartPart],
    ) -> None: ...

    async def abort_multipart_upload(self, storage_key: str, upload_id: str) -> None: ...

    async def list_multipart_parts(self, storage_key: str, upload_id: str) -> list[UploadedMultipartPart]: ...


__all__ = [
    "AsyncReadable",
    "MultipartPart",
    "MultipartStorage",
    "ObjectMeta",
    "ObjectStorage",
    "UploadedMultipartPart",
]
