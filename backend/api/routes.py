from fastapi import APIRouter, Query
from backend.core.linker import PaperLinker

router = APIRouter()
# 서버 실행 시 Linker 인스턴스를 한 번만 생성하여 메모리 및 DB 연결 효율화
linker = PaperLinker()

@router.get("/search")
async def search(
    query: str = Query(..., description="검색어 또는 ArXiv ID"), 
    mode: str = Query("통합 검색", description="검색 모드: 통합, 제목, 키워드, AI 시맨틱, 분야")
): 
    """
    [지능형 하이브리드 검색 엔드포인트]
    1. 사용자가 선택한 모드(mode)에 따라 DB에서 1차 검색을 수행합니다.
    2. 결과가 없고, '키워드 기반 모드'일 경우 실시간 Waterfall Sync를 가동합니다.
    """
    # 1. DB에서 먼저 모드에 맞춰 검색 (StorageManager.unified_search 호출)
    results = linker.search(query, mode)
    
    # 2. DB에 결과가 없는 경우 자동 동기화(Sync) 트리거
    # (주의: '분야'나 'AI 시맨틱'은 로컬 기반 탐색이므로, '통합/제목/키워드' 검색 시에만 자동 Sync 수행)
    if not results and mode in ["통합 검색", "제목(Title)", "키워드(Keyword)"]:
        print(f"INFO: '{query}'에 대한 로컬 데이터가 부족합니다. Waterfall Sync를 가동합니다.")
        
        # Waterfall 전략 실행 (HF -> ArXiv -> GitHub)
        await linker.sync_data(query) 
        
        # 3. 동기화가 완료된 후 최신화된 DB에서 다시 검색
        results = linker.search(query, mode)
        
    return results

@router.post("/sync")
async def sync(keyword: str):
    """사용자가 명시적으로 'New Sync' 버튼을 눌렀을 때 실행"""
    print(f"INFO: 사용자 요청에 의한 실시간 데이터 동기화 시작: {keyword}")
    count = linker.sync_data(keyword)
    return {"status": "success", "synced": count}

@router.post("/debug/reset")
async def reset_database():
    """개발 및 테스트용: DB와 벡터 저장소를 완전히 초기화"""
    try:
        linker.storage.reset_db()
        return {"status": "success", "message": "데이터베이스 및 컬렉션이 초기화되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}