"""
Storage abstraction. Local disk for development; swap the implementation of
save_file()/read_file() for boto3 (S3) or azure-storage-blob in production -
nothing else in the codebase needs to change since callers only use this module.
"""
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status, UploadFile

from app.core.config import settings


def validate_upload(file: UploadFile, content: bytes) -> str:
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {ext}")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({size_mb:.1f} MB). Max allowed is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )
    return ext


def save_file(company_id, content: bytes, ext: str) -> str:
    """Saves under uploads/<company_id>/<uuid><ext>, returns the relative path."""
    company_dir = Path(settings.UPLOAD_DIR) / str(company_id)
    company_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    full_path = company_dir / filename
    with open(full_path, "wb") as f:
        f.write(content)

    return str(full_path)


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
