"""
AWS S3 storage implementation.

Requires: boto3, aioboto3
Install via the s3 extra: uv tool install 'pyfastcms[s3]'

Configuration via environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_S3_BUCKET_NAME
- AWS_S3_REGION (optional, default: us-east-1)
- AWS_S3_ENDPOINT_URL (optional, for S3-compatible services)
"""

from io import BytesIO
from typing import BinaryIO, Optional

try:
    import aioboto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    aioboto3 = None
    ClientError = Exception

from .base import BaseStorage, DownloadError, StorageError, StorageFile, UploadError


class S3Storage(BaseStorage):
    """AWS S3 storage implementation."""

    def __init__(
        self,
        bucket_name: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        public_url: Optional[str] = None,
    ):
        """
        Initialize S3 storage.

        Args:
            bucket_name: S3 bucket name
            access_key_id: AWS access key ID (optional, uses env var if not provided)
            secret_access_key: AWS secret access key (optional, uses env var if not provided)
            region: AWS region (default: us-east-1)
            endpoint_url: Custom endpoint URL for S3-compatible services
            public_url: Custom public URL base for files
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 and aioboto3 are required for S3 storage. "
                "Install via the s3 extra: uv tool install 'pyfastcms[s3]'"
            )

        self.bucket_name = bucket_name
        self.region = region
        self.endpoint_url = endpoint_url
        self.public_url = public_url

        # Session configuration
        self.session = aioboto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def _get_client(self):
        """Get S3 client context manager."""
        return self.session.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
        )

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageFile:
        """Upload file to S3."""
        try:
            file.seek(0)
            content = file.read()
            size = len(content)

            extra_args = {
                "ContentType": content_type,
            }

            if metadata:
                # S3 metadata keys must be lowercase
                extra_args["Metadata"] = {k.lower(): str(v) for k, v in metadata.items()}

            async with self._get_client() as s3:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content,
                    **extra_args,
                )

            return StorageFile(
                key=key,
                size=size,
                content_type=content_type,
                url=self.get_public_url(key),
            )

        except ClientError as e:
            raise UploadError(f"Failed to upload to S3: {str(e)}") from e
        except Exception as e:
            raise UploadError(f"Failed to upload file: {str(e)}") from e

    async def download(self, key: str) -> bytes:
        """Download file from S3."""
        try:
            async with self._get_client() as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            raise DownloadError(f"Failed to download from S3: {str(e)}") from e
        except Exception as e:
            raise DownloadError(f"Failed to download file: {str(e)}") from e

    async def download_stream(self, key: str) -> BytesIO:
        """Download file as a stream."""
        content = await self.download(key)
        return BytesIO(content)

    async def delete(self, key: str) -> None:
        """Delete file from S3."""
        try:
            async with self._get_client() as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            raise StorageError(f"Failed to delete from S3: {str(e)}") from e
        except Exception as e:
            raise StorageError(f"Failed to delete file: {str(e)}") from e

    async def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            async with self._get_client() as s3:
                await s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise StorageError(f"Failed to check file existence: {str(e)}") from e

    async def get_metadata(self, key: str) -> StorageFile:
        """Get file metadata from S3."""
        try:
            async with self._get_client() as s3:
                response = await s3.head_object(Bucket=self.bucket_name, Key=key)

            return StorageFile(
                key=key,
                size=response["ContentLength"],
                content_type=response.get("ContentType", "application/octet-stream"),
                url=self.get_public_url(key),
                etag=response.get("ETag", "").strip('"'),
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"File not found: {key}")
            raise StorageError(f"Failed to get metadata: {str(e)}") from e
        except Exception as e:
            raise StorageError(f"Failed to get metadata: {str(e)}") from e

    def get_public_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """
        Get public URL for file.

        Args:
            key: File identifier
            expires_in: Expiration time in seconds (for presigned URLs)

        Returns:
            Public or presigned URL
        """
        if self.public_url:
            return f"{self.public_url}/{key}"

        # For private buckets, would generate presigned URL
        # For now, return the S3 URL format
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket_name}/{key}"

        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for temporary access.

        Args:
            key: File identifier
            expires_in: URL expiration in seconds (default: 1 hour)

        Returns:
            Presigned URL
        """
        try:
            async with self._get_client() as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
            return url
        except Exception as e:
            raise StorageError(f"Failed to generate presigned URL: {str(e)}") from e

    async def list_files(self, prefix: str = "", limit: int = 1000) -> list[StorageFile]:
        """List files in S3 bucket."""
        try:
            files = []
            async with self._get_client() as s3:
                paginator = s3.get_paginator("list_objects_v2")
                pages = paginator.paginate(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    PaginationConfig={"MaxItems": limit},
                )

                async for page in pages:
                    if "Contents" not in page:
                        break

                    for obj in page["Contents"]:
                        files.append(
                            StorageFile(
                                key=obj["Key"],
                                size=obj["Size"],
                                content_type="application/octet-stream",  # S3 list doesn't return content type
                                url=self.get_public_url(obj["Key"]),
                                etag=obj.get("ETag", "").strip('"'),
                            )
                        )

            return files

        except ClientError as e:
            raise StorageError(f"Failed to list files: {str(e)}") from e
        except Exception as e:
            raise StorageError(f"Failed to list files: {str(e)}") from e

    async def copy(self, source_key: str, dest_key: str) -> StorageFile:
        """Copy file within S3 bucket."""
        try:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}

            async with self._get_client() as s3:
                await s3.copy_object(
                    CopySource=copy_source,
                    Bucket=self.bucket_name,
                    Key=dest_key,
                )

            return await self.get_metadata(dest_key)

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Source file not found: {source_key}")
            raise StorageError(f"Failed to copy file: {str(e)}") from e
        except Exception as e:
            raise StorageError(f"Failed to copy file: {str(e)}") from e

    async def get_size(self, key: str) -> int:
        """Get file size from S3."""
        metadata = await self.get_metadata(key)
        return metadata.size
