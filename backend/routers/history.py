from fastapi import APIRouter, HTTPException

from services import db


router = APIRouter()


@router.get("/")
async def list_history():
    return await db.list_upload_history()


@router.get("/{entry_id}")
async def get_history(entry_id: int):
    entry = await db.get_upload_history(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return entry


@router.delete("/{entry_id}")
async def delete_history(entry_id: int):
    deleted = await db.delete_upload_history(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"success": True}