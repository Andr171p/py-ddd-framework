from typing import Any, BinaryIO

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager

from aiobotocore.client import AioBaseClient
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from ddf.application.exceptions import NotFoundError
from ddf.application.storage import AsyncReadable, MultipartPart, ObjectMeta, UploadedMultipartPart

from .config import DEFAULT_MIN_CHUNK_SIZE, MAX_PART_NUMBER, S3Config


class S3Client:
    def __init__(self, config: S3Config) -> None:
        self._config = config
        self.session = get_session()
        self._stack = AsyncExitStack()
        self._client: AioBaseClient | None = None
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> AioBaseClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    kwargs = {
                        "service_name": self._config.service_name,
                        "endpoint_url": str(self._config.endpoint_url),
                        "region_name": self._config.region,
                        "aws_access_key_id": self._config.access_key,
                        "aws_secret_access_key": self._config.secret_key.get_secret_value(),
                    }
                    self._client = await self._stack.enter_async_context(
                        self.session.create_client(
                            **kwargs,
                            config=AioConfig(s3={"addressing_style": self._config.addressing_style}),
                        )
                    )

        return self._client

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[AioBaseClient]:
        yield await self._ensure_client()

    async def close(self) -> None:
        await self._stack.aclose()
        self._client = None

    async def upload(self, file: bytes | BinaryIO, storage_key: str, content_type: str) -> None:
        async with self.get_client() as client:
            await client.put_object(
                Bucket=self._config.bucket,
                Body=file,
                Key=storage_key,
                ContentType=content_type,
            )

    async def delete(self, storage_key: str, *, version_id: str | None = None) -> None:
        params: dict[str, str] = {"Bucket": self._config.bucket, "Key": storage_key}
        if version_id is not None:
            params["VersionId"] = version_id

        async with self.get_client() as client:
            await client.delete_object(**params)

    async def delete_by_prefix(self, prefix: str) -> None:
        async with self.get_client() as client:
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(Bucket=self._config.bucket, Prefix=prefix):
                if objects_to_delete := [{"Key": obj["Key"]} for obj in page.get("Contents", [])]:
                    await client.delete_objects(
                        Bucket=self._config.bucket,
                        Delete={"Objects": objects_to_delete},
                    )

    async def create_upload_url(
        self,
        storage_key: str,
        content_type: str,
        checksum: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        params = {
            "Bucket": self._config.bucket,
            "Key": storage_key,
            "ContentType": content_type,
        }

        if checksum:
            params["ChecksumSHA256"] = checksum

        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )

    async def create_download_url(
        self,
        storage_key: str,
        expires_in: int = 3600,
        *,
        version_id: str | None = None,
    ) -> str:
        params: dict[str, str] = {"Bucket": self._config.bucket, "Key": storage_key}
        if version_id is not None:
            params["VersionId"] = version_id

        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )

    async def get_metadata(self, storage_key: str, *, version_id: str | None = None) -> ObjectMeta:
        params: dict[str, str] = {"Bucket": self._config.bucket, "Key": storage_key}
        if version_id is not None:
            params["VersionId"] = version_id

        try:
            async with self.get_client() as client:
                response = await client.head_object(**params)
                return ObjectMeta(
                    size=response["ContentLength"],
                    content_type=response["ContentType"],
                    last_modified=response["LastModified"],
                    checksum=response.get("ChecksumSHA256"),
                )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]

            if code in {"404", "NoSuchKey", "NotFound"}:
                raise NotFoundError(f"Object with key {storage_key!r} not found") from exc

            raise

    async def upload_stream(
        self,
        file_stream: AsyncReadable,
        storage_key: str,
        mime_type: str,
        chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    ) -> None:
        """Потоковая загрузка через Multipart upload."""

        if chunk_size < DEFAULT_MIN_CHUNK_SIZE:
            raise ValueError("chunk_size must be at least 5 MiB for S3 multipart upload.")

        async with self.get_client() as client:
            response = await client.create_multipart_upload(
                Bucket=self._config.bucket,
                Key=storage_key,
                ContentType=mime_type,
            )

            upload_id = response["UploadId"]
            parts: list[dict[str, Any]] = []

            try:
                part_number = 1

                while chunk := await file_stream.read(chunk_size):
                    part = await client.upload_part(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                    )

                    parts.append({"ETag": part["ETag"], "PartNumber": part_number})
                    part_number += 1

                if not parts:
                    await client.abort_multipart_upload(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        UploadId=upload_id,
                    )

                    await client.put_object(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        ContentType=mime_type,
                        Body=b"",
                    )
                    return

                await client.complete_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )

            except Exception:
                await client.abort_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                )
                raise

    async def download_stream(
        self,
        storage_key: str,
        chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
        *,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Потоковое чтение объекта из S3 - multipart download."""

        params: dict[str, str] = {"Bucket": self._config.bucket, "Key": storage_key}
        if version_id is not None:
            params["VersionId"] = version_id

        stack = AsyncExitStack()

        try:
            client = await stack.enter_async_context(self.get_client())
            response = await client.get_object(**params)

            body = response["Body"]

            try:
                while chunk := await body.read(chunk_size):
                    yield chunk
            finally:
                body.close()
        finally:
            await stack.aclose()

    async def create_multipart_upload(self, storage_key: str, content_type: str) -> str:
        async with self.get_client() as client:
            response = await client.create_multipart_upload(
                Bucket=self._config.bucket,
                Key=storage_key,
                ContentType=content_type,
            )
            return response["UploadId"]

    async def create_upload_part_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
        expires_in: int = 3600,
    ) -> str:
        if not 1 <= part_number <= MAX_PART_NUMBER:
            raise ValueError("part_number must be between 1 and 10000 for S3 multipart upload.")

        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self._config.bucket,
                    "Key": storage_key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )

    async def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: Sequence[MultipartPart],
    ) -> None:
        sorted_parts = sorted(parts, key=lambda part: part.part_number)
        s3_parts = [{"PartNumber": part.part_number, "ETag": part.etag} for part in sorted_parts]

        try:
            async with self.get_client() as client:
                await client.complete_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": s3_parts},
                )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in {"404", "NoSuchUpload"}:
                raise NotFoundError(
                    f"Multipart upload {upload_id!r} for key {storage_key!r} not found",
                ) from exc
            raise

    async def abort_multipart_upload(self, storage_key: str, upload_id: str) -> None:
        try:
            async with self.get_client() as client:
                await client.abort_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in {"404", "NoSuchUpload"}:
                raise NotFoundError(
                    f"Multipart upload {upload_id!r} for key {storage_key!r} not found",
                ) from exc
            raise

    async def list_multipart_parts(self, storage_key: str, upload_id: str) -> list[UploadedMultipartPart]:
        parts: list[UploadedMultipartPart] = []

        try:
            async with self.get_client() as client:
                paginator = client.get_paginator("list_parts")
                async for page in paginator.paginate(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                ):
                    parts.extend(
                        UploadedMultipartPart(
                            part_number=part["PartNumber"], etag=part["ETag"], size_bytes=part["Size"]
                        )
                        for part in page.get("Parts", [])
                    )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in {"404", "NoSuchUpload"}:
                raise NotFoundError(
                    f"Multipart upload {upload_id!r} for key {storage_key!r} not found",
                ) from exc
            raise

        return parts
