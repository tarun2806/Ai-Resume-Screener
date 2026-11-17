"""Private resume file storage.

Backends:
- LocalStorage: filesystem under STORAGE_DIR (default backend/data/resumes).
  Never web-accessed directly; downloads go through an authenticated endpoint.
- S3Storage: any S3-compatible bucket (requires boto3 + S3_BUCKET env).

Keys are server-generated opaque paths like ``{org_id}/{uuid}.{ext}`` -
never derived from candidate names/emails. All keys are validated against
traversal before use.
"""
import os
import re
import uuid
from functools import lru_cache

from app.config import settings

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_\-]{0,200}\.(pdf|docx|bin)$")


class StorageError(Exception):
    pass


def validate_key(key: str) -> str:
    """Reject anything that isn't a clean server-generated object key."""
    if not key or not _KEY_RE.match(key) or ".." in key:
        raise StorageError("Invalid storage key")
    return key


def generate_key(org_id, ext: str) -> str:
    """Opaque, tenant-namespaced key. Contains no PII."""
    ext = ext.lower() if ext.lower() in (".pdf", ".docx") else ".bin"
    return f"{org_id or 0}/{uuid.uuid4().hex}{ext}"


class StorageBackend:
    def put(self, key: str, content: bytes) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except Exception:
            return False


class LocalStorage(StorageBackend):
    """Filesystem storage rooted at a private directory."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        validate_key(key)
        path = os.path.abspath(os.path.join(self.root, key))
        if not path.startswith(self.root + os.sep):
            raise StorageError("Invalid storage key")
        return path

    def put(self, key: str, content: bytes) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(content)
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise StorageError("Object not found")

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass


class S3Storage(StorageBackend):
    """S3-compatible object storage (private bucket; no public URLs)."""

    def __init__(self):
        try:
            import boto3
        except ImportError as e:
            raise StorageError("boto3 is required for S3 storage") from e
        if not settings.s3_bucket:
            raise StorageError("S3_BUCKET is not configured")
        self.bucket = settings.s3_bucket
        kwargs = {"region_name": settings.s3_region}
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_access_key and settings.s3_secret_key:
            kwargs["aws_access_key_id"] = settings.s3_access_key
            kwargs["aws_secret_access_key"] = settings.s3_secret_key
        self._client = boto3.client("s3", **kwargs)
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the private bucket if absent (idempotent bootstrap)."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                kwargs = {"Bucket": self.bucket}
                if settings.s3_region not in ("us-east-1", "aws-global"):
                    kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": settings.s3_region}
                self._client.create_bucket(**kwargs)
            except Exception as e:
                # Race with another instance or already-owned bucket is fine.
                if "BucketAlready" not in str(e) and "AlreadyOwned" not in str(e):
                    raise StorageError("Could not provision storage bucket") from e

    def put(self, key: str, content: bytes) -> None:
        self._client.put_object(
            Bucket=self.bucket, Key=validate_key(key), Body=content,
            ServerSideEncryption="AES256",
        )

    def get(self, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=self.bucket, Key=validate_key(key))["Body"].read()
        except Exception as e:
            raise StorageError("Object not found") from e

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=validate_key(key))


def _default_root() -> str:
    if settings.storage_dir:
        return settings.storage_dir
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "resumes",
    )


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(_default_root())


def reset_storage_cache() -> None:
    """Test hook: drop the cached backend (e.g. after env changes)."""
    get_storage.cache_clear()
