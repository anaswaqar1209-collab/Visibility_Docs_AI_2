import os
import uuid
import hashlib
import aiofiles
from pathlib import Path
from fastapi import UploadFile
from ..config import settings
from ..database import SupabaseDB
from ..services.hf_storage import hf_storage

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".docx", ".xlsx", ".pptx"}
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def is_allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


import re

def generate_unique_filename(original: str) -> str:
    # Remove null bytes and control chars, replace Windows-invalid chars with _
    safe = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', original)
    safe = safe.strip().strip('.')
    safe = safe[:200]
    if not safe:
        safe = f"file_{uuid.uuid4().hex[:8]}"
    return safe


async def save_upload_file(upload_file: UploadFile, upload_dir: str = None) -> dict:
    if upload_dir is None:
        upload_dir = settings.UPLOAD_DIR

    os.makedirs(upload_dir, exist_ok=True)

    file_data = await upload_file.read()

    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB")

    filename = generate_unique_filename(upload_file.filename)

    hf_url = hf_storage.upload_bytes(file_data, filename)
    file_path = ""
    if hf_url:
        file_path = hf_url
    else:
        file_path = os.path.join(upload_dir, filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_data)

    supabase_url = ""
    try:
        SupabaseDB.upload_file("documents", filename, file_data, upload_file.content_type)
        supabase_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/documents/{filename}"
    except Exception:
        pass

    return {
        "filename": filename,
        "original_name": upload_file.filename,
        "file_path": file_path,
        "file_size": len(file_data),
        "file_hash": get_file_hash(file_data),
        "content_type": upload_file.content_type or "application/octet-stream",
        "supabase_url": supabase_url or hf_url,
    }


def ensure_dirs():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
