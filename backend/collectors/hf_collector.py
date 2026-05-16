import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

class HFCollector:
    def __init__(self):
        # HF API 엔드포인트 설정
        self.search_url = "https://huggingface.co/api/papers/search" 
        self.detail_url = "https://huggingface.co/api/papers" 
        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

    async def fetch_hf_papers(self, keyword: str, limit: int = 5):
        results = []
        
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
            try:
                print(f"DEBUG: [Async] HF 통합 검색 시작 -> {keyword}")
                # 1. 통합 검색 API 호출
                search_res = await client.get(self.search_url, params={"q": keyword, "limit": limit})
                search_res.raise_for_status()
                papers = search_res.json()

                for p in papers:
                    # [핵심] paper 객체 내부를 먼저 확인하여 이중 구조(Nesting) 방어
                    inner_paper = p.get('paper', {})
                    paper_id = inner_paper.get('id') or p.get('id')
                    
                    if not paper_id:
                        continue

                    try:
                        # 2. 상세 API 호출 (더 풍부한 데이터 확보)
                        detail_res = await client.get(f"{self.detail_url}/{paper_id}")
                        detail_res.raise_for_status()
                        details = detail_res.json()
                        
                        # 상세 데이터 역시 이중 구조일 수 있으므로 방어적 파싱
                        d_paper = details.get('paper', details) 

                        # --- 🛡️ [강화된 GitHub URL 추출기] ---
                        # 상세 데이터 우선 확인 후, 없으면 검색 결과에서 재확인
                        raw_repo = d_paper.get('githubRepo') or p.get('githubRepo')
                        github_url = None
                        
                        if raw_repo:
                            raw_repo = raw_repo.strip() # 공백 안전 제거
                            
                            # Case A: 전체 홈페이지 형식 (https://github.com/...)
                            if raw_repo.startswith("http"):
                                github_url = raw_repo
                            # Case B: 일반적인 HF 제공 형식 (owner/repo)
                            elif "/" in raw_repo:
                                github_url = f"https://github.com/{raw_repo}"
                            # Case C: 그 외 예기치 못한 문자열은 제외 (None 유지)
                        # ------------------------------------

                        # 3. 정규화된 데이터를 results 리스트에 추가
                        results.append({
                            "id": paper_id,
                            "title": d_paper.get('title') or p.get('title') or "No Title",
                            "summary": d_paper.get('summary') or p.get('summary') or "",
                            "published": (d_paper.get('publishedAt') or p.get('publishedAt') or "N/A")[:10],
                            "upvotes": d_paper.get('upvotes') or p.get('upvotes', 0),
                            "authors": ", ".join([a.get('name', 'Unknown') for a in d_paper.get('authors', [])]) if d_paper.get('authors') else "Unknown",
                            "github_url": github_url, # 정제된 URL 탑재 완료!
                            "hf_url": f"https://huggingface.co/papers/{paper_id}",
                            "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf", 
                            "source": "HF"
                        })
                        
                    except Exception as e:
                        print(f"WARNING: 상세 정보 로드 실패 ({paper_id}): {e}")
                        continue

            except Exception as e:
                print(f"ERROR: HF API 호출 중 오류 발생: {e}")
                
        return results