"""
Azure Blob Storage implementation.

Requires: azure-storage-blob, aiohttp
Install via the azure extra: uv tool install 'pyfastcms[azure]'

Configuration via environment variables:
- AZURE_STORAGE_CONNECTION_STRING (recommended)
OR
- AZURE_STORAGE_ACCOUNT_NAME
- AZURE_STORAGE_ACCOUNT_KEY
"""

from io import BytesIO
from app.utils.timeutils import utcnow
from typing import BinaryIO, Optional

try:
    from azure.storage.blob.aio import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceNotFoundError

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    BlobServiceClient = None
    ContainerClient = None
    ResourceNotFoundError = Exception

from .base import BaseStorage, DownloadError, StorageError, StorageFile, UploadError


class AzureBlobStorage(BaseStorage):
    """Azure Blob Storage implementation."""

    def __init__(
        self,
        container_name: str,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        public_url: Optional[str] = None,
    ):
        """
        Initialize Azure Blob Storage.

        Args:
            container_name: Azure container name
            connection_string: Azure connection string (recommended)
            account_name: Storage account name (if not using connection string)
            account_key: Storage account key (if not using connection string)
            public_url: Custom public URL base for files
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required for Azure Blob Storage. "
                "Install via the azure extra: uv tool install 'pyfastcms[azure]'"
            )

        self.container_name = container_name
        self.public_url = public_url

        # Initialize BlobServiceClient
        if connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=account_key,
            )
        else:
            raise ValueError(
                "Either connection_string or (account_name + account_key) must be provided"
            )

        self.container_client: ContainerClient = self.blob_service_client.get_container_client(
            container_name
        )

    async def _ensure_container_exists(self):
        """Ensure the container exists, create if it doesn't."""
        try:
            await self.container_client.create_container()
        except Exception:
            # Container already exists or insufficient permissions
            pass

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageFile:
        """Upload file to Azure Blob Storage."""
        try:
            await self._ensure_container_exists()

            file.seek(0)
            content = file.read()
            size = len(content)

            blob_client = self.container_client.get_blob_client(key)

            # Prepare metadata
            azure_metadata = {}
            if metadata:
                # Azure metadata keys must be valid C# identifiers
                azure_metadata = {
                    k.replace("-", "_").replace(" ", "_"): str(v) for k, v in metadata.items()
                }

            await blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings={"content_type": content_type},
                metadata=azure_metadata,
            )

            return StorageFile(
                key=key,
                size=size,
                content_type=content_type,
                url=self.get_public_url(key),
            )

        except Exception as e:
            raise UploadError(f"Failed to upload to Azure: {str(e)}") from e

    async def download(self, key: str) -> bytes:
        """Download file from Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(key)
            stream = await blob_client.download_blob()
            content = await stream.readall()
            return content

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {key}")
        except Exception as e:
            raise DownloadError(f"Failed to download from Azure: {str(e)}") from e

    async def download_stream(self, key: str) -> BytesIO:
        """Download file as a stream."""
        content = await self.download(key)
        return BytesIO(content)

    async def delete(self, key: str) -> None:
        """Delete file from Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(key)
            await blob_client.delete_blob()

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {key}")
        except Exception as e:
            raise StorageError(f"Failed to delete from Azure: {str(e)}") from e

    async def exists(self, key: str) -> bool:
        """Check if file exists in Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(key)
            await blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            raise StorageError(f"Failed to check file existence: {str(e)}") from e

    async def get_metadata(self, key: str) -> StorageFile:
        """Get file metadata from Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(key)
            properties = await blob_client.get_blob_properties()

            return StorageFile(
                key=key,
                size=properties.size,
                content_type=properties.content_settings.content_type
                or "application/octet-stream",
                url=self.get_public_url(key),
                etag=properties.etag.strip('"') if properties.etag else None,
            )

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {key}")
        except Exception as e:
            raise StorageError(f"Failed to get metadata: {str(e)}") from e

    def get_public_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get public URL for file."""
        if self.public_url:
            return f"{self.public_url}/{key}"

        # Azure blob URL format
        blob_url = self.container_client.get_blob_client(key).url
        return blob_url

    async def get_sas_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a SAS (Shared Access Signature) URL for temporary access.

        Args:
            key: File identifier
            expires_in: URL expiration in seconds (default: 1 hour)

        Returns:
            SAS URL
        """
        try:
            from datetime import timedelta
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            blob_client = self.container_client.get_blob_client(key)

            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self.container_name,
                blob_name=key,
                account_key=blob_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=utcnow() + timedelta(seconds=expires_in),
            )

            return f"{blob_client.url}?{sas_token}"

        except Exception as e:
            raise StorageError(f"Failed to generate SAS URL: {str(e)}") from e

    async def list_files(self, prefix: str = "", limit: int = 1000) -> list[StorageFile]:
        """List files in Azure container."""
        try:
            files = []
            count = 0

            async for blob in self.container_client.list_blobs(name_starts_with=prefix):
                if count >= limit:
                    break

                files.append(
                    StorageFile(
                        key=blob.name,
                        size=blob.size,
                        content_type=blob.content_settings.content_type
                        if blob.content_settings
                        else "application/octet-stream",
                        url=self.get_public_url(blob.name),
                        etag=blob.etag.strip('"') if blob.etag else None,
                    )
                )
                count += 1

            return files

        except Exception as e:
            raise StorageError(f"Failed to list files: {str(e)}") from e

    async def copy(self, source_key: str, dest_key: str) -> StorageFile:
        """Copy file within Azure container."""
        try:
            source_blob = self.container_client.get_blob_client(source_key)
            dest_blob = self.container_client.get_blob_client(dest_key)

            # Check if source exists
            try:
                await source_blob.get_blob_properties()
            except ResourceNotFoundError:
                raise FileNotFoundError(f"Source file not found: {source_key}")

            # Copy blob
            source_url = source_blob.url
            await dest_blob.start_copy_from_url(source_url)

            return await self.get_metadata(dest_key)

        except FileNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to copy file: {str(e)}") from e

    async def get_size(self, key: str) -> int:
        """Get file size from Azure."""
        metadata = await self.get_metadata(key)
        return metadata.size

    async def close(self):
        """Close the blob service client."""
        await self.blob_service_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
