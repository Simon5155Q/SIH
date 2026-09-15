from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from app.services.storage_service import save_file, StorageError
from app.dependencies.auth import require_role

router = APIRouter(prefix="/uploads", tags=["uploads"])

@router.post("/inspection-photo")
async def upload_inspection_photo(
    file: UploadFile = File(...),
    current_user=Depends(require_role("LMO", "GATC")),
):
    try:
        path = await save_file(file, subfolder="inspection_photos")
    except StorageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"file_path": path}
