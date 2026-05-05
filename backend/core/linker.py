from backend.collectors.arxiv_collector import fetch_arxiv, extract_github_from_pdf
from backend.collectors.github_collector import fetch_github_link
from backend.collectors.hf_collector import fetch_hf_by_arxiv_id
from backend.core.embedder import PaperEmbedder
from backend.core.vector_db import StorageManager

class PaperLinker:
    def __init__(self):
        # RTX 5070의 성능을 활용할 임베더와 데이터 저장소 초기화
        self.embedder = PaperEmbedder()
        self.storage = StorageManager()

    def sync_data(self, keyword: str):
        """
        [Step 1-4] 논문 데이터를 수집하고 관련 자산(GitHub, HF)을 매칭하여 DB에 저장합니다.
        """
        # 1. ArXiv 기본 정보 수집
        papers = fetch_arxiv(keyword)
        print(f"'{keyword}' 주제로 {len(papers)}개의 논문을 분석합니다.")

        for p in papers:
            github_url = None
            hf_url = None

            # [Tier 1] ArXiv Comment 필드에서 GitHub 주소 확인
            github_url = getattr(p, 'temp_github_from_comment', None)
            
            # [Tier 2] Hugging Face API를 통해 모델/데이터셋 확인
            hf_url = fetch_hf_by_arxiv_id(p.id)

            # [Tier 3] PDF Smart Scan (PDF 본문 내 github.io 등 탐색)
            if not github_url:
                found_url = extract_github_from_pdf(p.pdf_url)
                if found_url:
                    print(f"[Found in PDF] {p.title[:20]}... -> {found_url}")
                    github_url = found_url

            # [Tier 4] GitHub API 검색 (최후의 수단)
            if not github_url:
                github_url = fetch_github_link(p.title)

            # 저장 직전 최종 확인 로그
            print(f"[DB Save Check] Paper: {p.id} | GitHub: {github_url} | HF: {hf_url}")

            # 5. 벡터 임베딩 생성 및 통합 저장
            vector = self.embedder.encode(p.summary)
            self.storage.save_all(p, vector, github_url, hf_url)
            print(f"동기화 완료: {p.title[:40]}...")

        return len(papers)

    def search(self, query: str):
        """
        UI에서 입력한 키워드로 저장된 데이터를 검색합니다.
        """
        # [수정 포인트] vector_db.py에 새로 만든 키워드 검색 함수를 호출합니다.
        # 기존에 에러가 났던 get_papers_by_ids 대신 이 함수를 사용합니다.
        return self.storage.search_papers_fuzzy(query)