from typing import Any, BinaryIO

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from aiobotocore.client import AioBaseClient
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from ddf.application.exceptions import NotFoundError
from ddf.application.storage import AsyncReadable, ObjectMeta

from .config import DEFAULT_MIN_CHUNK_SIZE, S3Config


class S3Client:
    def __init__(self, config: S3Config) -> None:
        self._config = config
        self.session = get_session()

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[AioBaseClient]:
        kwargs = {
            "service_name": self._config.service_name,
            "endpoint_url": str(self._config.endpoint_url),
            "region_name": self._config.region,
            "aws_access_key_id": self._config.access_key,
            "aws_secret_access_key": self._config.secret_key.get_secret_value(),
        }
        async with self.session.create_client(
            **kwargs, config=AioConfig(s3={"addressing_style": self._config.addressing_style})
        ) as client:
            yield client

    async def upload(self, file: bytes | BinaryIO, storage_key: str, content_type: str) -> None:
        async with self.get_client() as client:
            await client.put_object(
                Bucket=self._config.bucket,
                Body=file,
                Key=storage_key,
                ContentType=content_type,
            )

    async def delete(self, storage_key: str) -> None:
        async with self.get_client() as client:
            await client.delete_object(Bucket=self._config.bucket, Key=storage_key)

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

    async def create_download_url(self, storage_key: str, expires_in: int = 3600) -> str:
        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": storage_key},
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )

    async def get_metadata(self, storage_key: str) -> ObjectMeta:
        try:
            async with self.get_client() as client:
                response = await client.head_object(Bucket=self._config.bucket, Key=storage_key)
                return ObjectMeta(
                    size=response["ContentLength"],
                    content_type=response["ContentType"],
                    last_modified=response["LastModified"],
                    checksum=response.get("ChecksumSHA256"),
                )
        except ClientError:
            raise NotFoundError(f"Object with key {storage_key!r} not found") from None

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
    ) -> AsyncIterator[bytes]:
        """Потоковое чтение объекта из S3 - multipart download."""

        stack = AsyncExitStack()

        try:
            client = await stack.enter_async_context(self.get_client())
            response = await client.get_object(Bucket=self._config.bucket, Key=storage_key)

            body = response["Body"]

            try:
                while chunk := await body.read(chunk_size):
                    yield chunk
            finally:
                body.close()
        finally:
            await stack.aclose()
