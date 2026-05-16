import asyncio
from backend.collectors.arxiv_collector import extract_github_from_pdf, extract_from_comment, get_metadata_by_id, fetch_arxiv
from backend.collectors.github_collector import fetch_github_link
from backend.collectors.hf_collector import HFCollector
from backend.core.embedder import PaperEmbedder
from backend.core.vector_db import StorageManager
from backend.models.paper import PaperModel 

class PaperLinker:
    def __init__(self):
        self.embedder = PaperEmbedder()
        self.storage = StorageManager()
        self.hf_collector = HFCollector()

    async def sync_data(self, keyword: str):
        """
        [Optimized Waterfall & Enrichment Strategy]
        Stage 1. HF 우선 수집 및 ID 기반 고속 보완 (Comment -> PDF Scan)
        Stage 2. 결과 부족 시 ArXiv 키워드 검색으로 데이터 영토 확장
        Stage 3. 다계층 코드 탐색 (Comment -> PDF Scan -> GitHub API)
        """
        print(f"--- [{keyword}] 동기화 가동 (ID-First Waterfall) ---")
        total_saved = 0
        verified_assets_count = 0 

        # --- [Stage 1] Hugging Face 수집 및 ID 기반 정밀 보완 ---
        print("Stage 1. HF 수집 및 ID 기반 고속 보완 중...")
        hf_raw_data = await self.hf_collector.fetch_hf_papers(keyword, limit=5)
        
        for data in hf_raw_data:
            # 1. HF 자체 데이터 확인
            github_url = data.get('github_url')
            
            # 2. 코드가 없다면 ArXiv ID로 즉시 보완 (Enrichment)
            if not github_url:
                arxiv_id = data['id']
                print(f"🔍 [Enrichment] {arxiv_id} 보완 시작 (ID 기반)")
                
                # [Optimization] ID로 메타데이터(Comment)만 빠르게 가져오기
                arxiv_meta = await get_metadata_by_id(arxiv_id)
                if arxiv_meta:
                    # Tier 1: 저자 코멘트 확인 (가장 빠름)
                    github_url = extract_from_comment(arxiv_meta.get('comment'))
                    
                    # Tier 2: 코멘트에 없으면 PDF 본문 스캔
                    if not github_url:
                        print(f"📑 [Enrichment] Comment에 없음 -> PDF 본문 스캔: {arxiv_id}")
                        github_url = await extract_github_from_pdf(arxiv_meta.get('pdf_url'))
                    
                    data['github_url'] = github_url

            # DB 저장 및 벡터 임베딩
            paper_obj = PaperModel(**data)
            vector = self.embedder.encode(paper_obj.summary)
            self.storage.save_all(paper_obj.model_dump(), vector)
            total_saved += 1
            
            if paper_obj.github_url:
                verified_assets_count += 1
                print(f"✅ [HF+Alpha] {paper_obj.id} 확보 | Code: {paper_obj.github_url}")

        # [조기 종료] 코드 자산이 충분(2개 이상)하면 종료
        if verified_assets_count >= 2:
            print(f"INFO: 고품질 자산 확보로 조기 종료합니다. (총 {total_saved}개)")
            return total_saved

        # --- [Stage 2] ArXiv Fallback ---
        print("Stage 2. ArXiv 키워드 검색으로 추가 데이터 확보 중...")
        arxiv_papers = fetch_arxiv(keyword) 

        for p in arxiv_papers:
            # [수정] p.id 대신 entry_id에서 ID만 추출 (예: http://arxiv.org/abs/2110.03183v1 -> 2110.03183)
            p_id = p.entry_id.split('/')[-1].split('v')[0]
            
            # 중복 체크
            if self._is_already_saved(p_id):
                continue
            
            # [Stage 3] 다계층 코드 탐색
            github_url = getattr(p, 'temp_github_from_comment', None)
            
            if not github_url:
                github_url = await extract_github_from_pdf(p.pdf_url)

            if not github_url:
                github_url = await fetch_github_link(p.title)

            # [수정] PaperModel 생성 시에도 p_id 사용
            paper_obj = PaperModel(
                id=p_id,
                title=p.title,
                summary=p.summary,
                authors=", ".join([a.name for a in p.authors]) if hasattr(p, 'authors') else "Unknown",
                pdf_url=p.pdf_url,
                published=str(p.published.date()) if hasattr(p.published, 'date') else str(p.published),
                github_url=github_url,
                hf_url=None, 
                source="ArXiv",
                upvotes=0
            )

            vector = self.embedder.encode(paper_obj.summary)
            self.storage.save_all(paper_obj.model_dump(), vector)
            total_saved += 1
            print(f"➕ [ArXiv Added] {p_id} 확보")

        print(f"--- 동기화 종료: 총 {total_saved}개 업데이트 ---")
        return total_saved

    def _is_already_saved(self, paper_id: str):
        res = self.storage.conn.execute("SELECT id FROM papers WHERE id=?", (paper_id,)).fetchone()
        return res is not None

    def search(self, query: str, mode: str):
        return self.storage.unified_search(query, mode)