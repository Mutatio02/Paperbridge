from fastapi import APIRouter, Query
from backend.core.linker import PaperLinker

router = APIRouter()
linker = PaperLinker()

@router.get("/search")
async def search(query: str = Query(..., alias="query")): 
    data = linker.search(query)
    return data

@router.post("/sync")
async def sync(keyword: str):
    count = linker.sync_data(keyword)
    return {"status": "success", "synced": count}

# backend/api/routes.py
@router.post("/debug/reset")
async def reset_database():
    linker.storage.reset_db()
    return {"message": "Database reset successfully."}

# DB에 값이 없을때 찾기
@router.get("/search")
async def search(query: str):
    # 1. 일단 DB에서 먼저 찾아봅니다.
    results = linker.search(query)
    
    # 2. 만약 DB에 결과가 없다면? 
    if not results:
        print(f"'{query}' 결과 없음. 실시간 동기화를 시작합니다...")
        # 백엔드 내부에서 sync_data 함수를 직접 실행
        linker.sync_data(query) 
        
        # 3. 동기화가 끝난 후 다시 DB에서 데이터를 가져옵니다.
        results = linker.search(query)
        
    return results