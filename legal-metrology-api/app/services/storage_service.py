import aiofiles
import os
import uuid
from fastapi import UploadFile
from app.core.config import settings

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILE_SIZE_MB = 10

class StorageError(Exception):
    pass

async def save_file_local(file: UploadFile, subfolder: str = "misc") -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise StorageError(f"Extension {ext} not allowed")
    target_dir = os.path.join(settings.LOCAL_UPLOAD_DIR, subfolder)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(target_dir, filename)
    size = 0
    async with aiofiles.open(filepath, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await out_file.close()
                os.remove(filepath)
                raise StorageError("File exceeds max size limit")
            await out_file.write(chunk)
    return f"/uploads/{subfolder}/{filename}"

async def save_file_supabase(file: UploadFile, subfolder: str = "misc") -> str:
    from supabase import create_client
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise StorageError(f"Extension {ext} not allowed")
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    filename = f"{subfolder}/{uuid.uuid4().hex}{ext}"
    content = await file.read()
    client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
        filename, content, {"content-type": file.content_type}
    )
    return client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(filename)

async def save_file(file: UploadFile, subfolder: str = "misc") -> str:
    if getattr(settings, "STORAGE_PROVIDER", "local") == "supabase":
        return await save_file_supabase(file, subfolder)
    return await save_file_local(file, subfolder)
