import os

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


class UploadValidationError(ValueError):
    pass


def validate_upload(filename: str, content: bytes) -> str:
    """
    Validate an uploaded resume file.
    Returns the normalized extension. Raises UploadValidationError.
    """
    if not filename:
        raise UploadValidationError("Missing filename")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type '{ext}'. Only .pdf and .docx are allowed."
        )

    if len(content) == 0:
        raise UploadValidationError("Uploaded file is empty")

    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadValidationError("File exceeds the 5 MB size limit")

    # Magic-byte sniffing (extension alone is not trustworthy)
    head = content[:8]
    if ext == ".pdf" and not head.lstrip().startswith(b"%PDF"):
        raise UploadValidationError("File content does not look like a valid PDF")
    if ext == ".docx" and not head.startswith(b"PK\x03\x04"):
        raise UploadValidationError("File content does not look like a valid DOCX")

    return ext


async def read_and_validate(file) -> bytes:
    """Read an UploadFile with a hard size cap, then validate it."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    validate_upload(file.filename or "", content)
    return content


def ensure_uploads_enabled() -> None:
    """Reject uploads when UPLOADS_ENABLED=false (public demo mode).
    Raises fastapi.HTTPException 403."""
    from fastapi import HTTPException
    from app.config import settings

    if not settings.uploads_enabled:
        raise HTTPException(
            status_code=403,
            detail="Resume uploads are disabled on this public demo deployment",
        )
