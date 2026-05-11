"""
Storage module - Multi-backend file storage system.

Supports:
- Local filesystem (default, always available)
- AWS S3 (requires: boto3, aioboto3)
- Azure Blob Storage (requires: azure-storage-blob)

Usage:
    from app.services.storage import get_storage

    storage = get_storage()  # Uses config from settings

    # Upload
    with open('file.jpg', 'rb') as f:
        file_info = await storage.upload(f, 'uploads/file.jpg', 'image/jpeg')

    # Download
    content = await storage.download('uploads/file.jpg')

    # Delete
    await storage.delete('uploads/file.jpg')
"""

from typing import Optional

from app.core.config import settings

from .base import BaseStorage, DownloadError, StorageError, StorageFile, UploadError
from .local import LocalStorage

__all__ = [
    "BaseStorage",
    "LocalStorage",
    "S3Storage",
    "AzureBlobStorage",
    "StorageFile",
    "StorageError",
    "UploadError",
    "DownloadError",
    "get_storage",
]


# Lazy imports for optional dependencies
def get_s3_storage_class():
    """Lazy import S3Storage to avoid import errors if boto3 not installed."""
    try:
        from .s3 import S3Storage

        return S3Storage
    except ImportError as e:
        raise ImportError(
            "boto3 and aioboto3 are required for S3 storage. "
            f"Install with: uv tool install 'pyfastcms[s3]' (or pip install boto3 aioboto3)\n"
            f"Original error: {str(e)}"
        )


def get_azure_storage_class():
    """Lazy import AzureBlobStorage to avoid import errors if azure not installed."""
    try:
        from .azure import AzureBlobStorage

        return AzureBlobStorage
    except ImportError as e:
        raise ImportError(
            "azure-storage-blob is required for Azure Blob Storage. "
            f"Install with: uv tool install 'pyfastcms[azure]' (or pip install azure-storage-blob aiohttp)\n"
            f"Original error: {str(e)}"
        )


# Export with lazy loading
class S3Storage:
    """Proxy class for lazy loading S3Storage."""

    def __new__(cls, *args, **kwargs):
        S3StorageClass = get_s3_storage_class()
        return S3StorageClass(*args, **kwargs)


class AzureBlobStorage:
    """Proxy class for lazy loading AzureBlobStorage."""

    def __new__(cls, *args, **kwargs):
        AzureBlobStorageClass = get_azure_storage_class()
        return AzureBlobStorageClass(*args, **kwargs)


def get_storage(storage_type: Optional[str] = None) -> BaseStorage:
    """
    Get storage backend based on configuration.

    Args:
        storage_type: Override storage type (local, s3, azure).
                     If None, uses STORAGE_TYPE from settings.

    Returns:
        Configured storage backend

    Raises:
        ValueError: If storage type is invalid or required config is missing
        ImportError: If required dependencies are not installed

    Examples:
        # Use default from settings
        storage = get_storage()

        # Force local storage
        storage = get_storage('local')

        # Force S3
        storage = get_storage('s3')
    """
    storage_type = storage_type or settings.STORAGE_TYPE

    if storage_type == "local":
        return LocalStorage(
            base_path=settings.LOCAL_STORAGE_PATH,
            base_url=settings.BASE_URL,
        )

    elif storage_type == "s3":
        # Validate S3 configuration
        if not settings.AWS_S3_BUCKET_NAME:
            raise ValueError("AWS_S3_BUCKET_NAME is required for S3 storage")

        S3StorageClass = get_s3_storage_class()
        return S3StorageClass(
            bucket_name=settings.AWS_S3_BUCKET_NAME,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region=settings.AWS_S3_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            public_url=settings.AWS_S3_PUBLIC_URL,
        )

    elif storage_type == "azure":
        # Validate Azure configuration
        if not settings.AZURE_STORAGE_CONTAINER_NAME:
            raise ValueError("AZURE_STORAGE_CONTAINER_NAME is required for Azure storage")

        if not (
            settings.AZURE_STORAGE_CONNECTION_STRING
            or (settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY)
        ):
            raise ValueError(
                "Either AZURE_STORAGE_CONNECTION_STRING or "
                "(AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY) is required"
            )

        AzureBlobStorageClass = get_azure_storage_class()
        return AzureBlobStorageClass(
            container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
            connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            public_url=settings.AZURE_STORAGE_PUBLIC_URL,
        )

    else:
        raise ValueError(
            f"Invalid storage type: {storage_type}. "
            f"Must be one of: local, s3, azure"
        )


# Convenience function for getting default storage
def get_default_storage() -> BaseStorage:
    """
    Get the default configured storage backend.

    This is a convenience function that calls get_storage()
    with no arguments.

    Returns:
        Default storage backend from settings
    """
    return get_storage()
