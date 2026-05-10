from backend.collectors.arxiv_collector import fetch_arxiv, extract_github_from_pdf
from backend.collectors.github_collector import fetch_github_link
from backend.collectors.hf_collector import HFCollector  # REST API 버전 클래스
from backend.core.embedder import PaperEmbedder
from backend.core.vector_db import StorageManager
from backend.models.paper import PaperModel 

class PaperLinker:
    def __init__(self):
        # RTX 5070의 자원을 효율적으로 사용하기 위해 인스턴스는 한 번만 생성
        self.embedder = PaperEmbedder()
        self.storage = StorageManager()
        self.hf_collector = HFCollector() # REST API 기반 수집기

    async def sync_data(self, keyword: str):
        """
        [Waterfall Retrieval Strategy]
        Step 1. Hugging Face에서 검증된 자산(논문+코드+모델) 우선 확보
        Step 2. 결과 부족 시 ArXiv 탐색 및 다계층(Tiered) 코드 검색 가동
        """
        print(f"--- [{keyword}] 동기화 시작 (Waterfall 전략) ---")
        total_saved = 0
        verified_assets_count = 0  # 실제로 코드/모델이 있는 논문 수
        
        # --- [Step 1] Hugging Face 우선 탐색 (High Precision) ---
        print("Step 1. Hugging Face REST API 사냥 중...")
        hf_raw_data = await self.hf_collector.fetch_hf_papers(keyword, limit=5)
        
        for data in hf_raw_data:
            paper_obj = PaperModel(**data)
            
            # 실제 자산(GitHub)이 있는지 확인
            has_code = bool(paper_obj.github_url)
            print(f"[HF Found] {paper_obj.title[:30]}... | Code: {has_code}")
            
            vector = self.embedder.encode(paper_obj.summary)
            self.storage.save_all(paper_obj.model_dump(), vector)
            total_saved += 1
            
            if has_code:
                verified_assets_count += 1

        # [수정된 조기 종료 조건]
        # 단순히 3개가 아니라, '공식 코드 링크가 포함된 논문'이 1개라도 있을 때만 종료하거나
        # 검색어와 제목이 어느 정도 유사할 때 종료하는 로직이 필요합니다.
        if verified_assets_count >= 1: 
            print(f"INFO: 코드 자산이 포함된 고품질 데이터를 확보하여 Sync를 종료합니다.")
            return total_saved

        # --- [Step 2] ArXiv Fallback (High Recall) ---
        print("Step 2. 결과 보충을 위해 ArXiv 및 다계층 코드 탐색 시작...")
        arxiv_papers = fetch_arxiv(keyword)
        
        for p in arxiv_papers:
            # 중복 체크: 이미 HF 단계에서 저장된 논문이면 건너뜀 (ArXiv ID 기준)
            if self._is_already_saved(p.id):
                continue
            
            # 다계층 코드 검색 (Tiered Search)
            github_url = getattr(p, 'temp_github_from_comment', None)
            
            # [Tier 3] PDF 본문 스캔 (HF에 정보가 없을 때만 실행)
            if not github_url:
                github_url = extract_github_from_pdf(p.pdf_url)

            # [Tier 4] GitHub API 검색 (최후의 수단)
            if not github_url:
                github_url = fetch_github_link(p.title)

            print(f"[ArXiv Fallback] {p.id} 매칭 중 | GitHub: {bool(github_url)}")

            # ArXiv에서 가져온 객체를 PaperModel 규격으로 변환
            paper_obj = PaperModel(
                id=p.id,
                title=p.title,
                summary=p.summary,
                authors=", ".join([a.name for a in p.authors]) if hasattr(p, 'authors') else "Unknown",
                pdf_url=p.pdf_url,
                published=str(p.published),
                github_url=github_url,
                hf_url=None, # ArXiv 단독 데이터이므로 모델 링크는 초기값
                source="ArXiv",
                upvotes=0,
                temp_github_from_comment=getattr(p, 'temp_github_from_comment', None)
            )

            # 임베딩 생성 및 저장
            vector = self.embedder.encode(paper_obj.summary)
            self.storage.save_all(paper_obj.model_dump(), vector)
            total_saved += 1
            
        print(f"--- 동기화 완료: 총 {total_saved}개 논문 업데이트 ---")
        return total_saved

    def _is_already_saved(self, paper_id: str):
        """DB 중복 확인용 헬퍼 함수"""
        res = self.storage.conn.execute("SELECT id FROM papers WHERE id=?", (paper_id,)).fetchone()
        return res is not None

    def search(self, query: str, mode: str):
        """프론트엔드 대시보드 모드에 따른 통합 검색"""
        return self.storage.unified_search(query, mode)