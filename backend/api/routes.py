from fastapi import APIRouter
from backend.core.linker import PaperLinker

router = APIRouter()
linker = PaperLinker()

@router.get("/search")
async def search(q: str):
    data = linker.search(q)
    return {"status": "success", "results": data}

@router.post("/sync")
async def sync(keyword: str):
    count = linker.sync_data(keyword)
    return {"status": "success", "synced": count}

# backend/api/routes.py
@router.post("/debug/reset")
async def reset_database():
    linker.storage.reset_db()
    return {"message": "Database reset successfully."}