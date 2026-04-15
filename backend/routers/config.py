from fastapi import APIRouter, HTTPException

from models.schemas import ProfileRequest
from services import db
from services import azdo


router = APIRouter()


@router.get("/profiles")
async def list_profiles():
    return await db.list_profiles()


@router.get("/profiles/{name}")
async def get_profile(name: str):
    profile = await db.get_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/profiles")
async def save_profile(req: ProfileRequest):
    await db.save_profile(req.name, req.config.model_dump())
    return {"success": True, "name": req.name}


@router.delete("/profiles/{name}")
async def delete_profile(name: str):
    deleted = await db.delete_profile(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"success": True}


@router.post("/validate")
async def validate_connection(req: ProfileRequest):
    try:
        suites = await azdo.fetch_suites(req.config)
        return {
            "connected": True,
            "suite_count": len(suites),
            "plan_id": req.config.plan_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc