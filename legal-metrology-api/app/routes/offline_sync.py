from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
from app.dependencies.auth import require_role
from app.utils.geo import is_within_geofence

router = APIRouter(prefix="/inspections", tags=["inspections"])

class InspectionSyncItem(BaseModel):
    local_id: str
    instrument_serial: str
    officer_lat: float
    officer_lon: float
    shop_lat: float
    shop_lon: float
    status: str
    inspected_at: str

@router.post("/sync-batch")
async def sync_offline_inspections(
    records: List[InspectionSyncItem],
    current_user=Depends(require_role("LMO"))
):
    """Processes batched inspection records queued while field officers were offline."""
    synced = []
    rejected = []

    for item in records:
        if not is_within_geofence(item.officer_lat, item.officer_lon, item.shop_lat, item.shop_lon):
            rejected.append({
                "local_id": item.local_id,
                "reason": "Geo-fencing validation failed: Officer was out of perimeter"
            })
            continue
        
        synced.append(item.local_id)

    return {
        "total_received": len(records),
        "synced_count": len(synced),
        "synced_ids": synced,
        "rejected": rejected
    }
