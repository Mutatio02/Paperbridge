from backend.collectors.arxiv_collector import fetch_arxiv, extract_github_from_pdf
from backend.collectors.github_collector import fetch_github_link
from backend.collectors.hf_collector import fetch_hf_by_arxiv_id
from backend.core.embedder import PaperEmbedder
from backend.core.vector_db import StorageManager

class PaperLinker:
    def __init__(self):
        self.embedder = PaperEmbedder()
        self.storage = StorageManager()

    def sync_data(self, keyword: str):
        # 1. ArXiv 기본 정보 수집 (Comment 필드 포함)
        papers = fetch_arxiv(keyword)
        print(f"'{keyword}' 주제로 {len(papers)}개의 논문을 분석합니다.")

        for p in papers:
            github_url = None
            hf_url = None

            # [Tier 1] Comment
            github_url = getattr(p, 'temp_github_from_comment', None)
            
            # [Tier 2] HF
            hf_url = fetch_hf_by_arxiv_id(p.id)

            # [Tier 3] PDF Smart Scan
            if not github_url:
                found_url = extract_github_from_pdf(p.pdf_url)
                if found_url:
                    print(f"[Found in PDF] {p.title[:20]}... -> {found_url}")
                    github_url = found_url

            # [Tier 4] GitHub API
            if not github_url:
                github_url = fetch_github_link(p.title)

            # 저장 직전 최종 확인 로그
            print(f"[DB Save Check] Paper: {p.id} | GitHub: {github_url} | HF: {hf_url}")

            vector = self.embedder.encode(p.summary)
            self.storage.save_all(p, vector, github_url, hf_url)
            print(f"동기화 완료: {p.title[:40]}...")

        return len(papers)

    def search(self, query: str):
        # 사용자의 질문을 벡터로 변환하여 시맨틱 검색 수행
        query_vec = self.embedder.encode(query)
        ids = self.storage.search_similar_ids(query_vec)
        return self.storage.get_papers_by_ids(ids)