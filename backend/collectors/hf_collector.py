import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

class HFCollector:
    def __init__(self):
        self.search_url = "https://huggingface.co/api/papers/search" # Search Papers
        self.detail_url = "https://huggingface.co/api/papers"
        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

    async def fetch_hf_papers(self, keyword: str, limit: int = 5):
        results = []
        
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
            try:
                print(f"DEBUG: [Async] HF 통합 검색 시작 -> {keyword}")
                search_res = await client.get(self.search_url, params={"q": keyword, "limit": limit})
                search_res.raise_for_status()
                papers = search_res.json()

                for p in papers:
                    # [핵심 수정] paper 객체 내부를 먼저 확인하고, 없으면 루트를 확인합니다.
                    inner_paper = p.get('paper', {})
                    
                    # ID 추출 (p['paper']['id'] 혹은 p['id'])
                    paper_id = inner_paper.get('id') or p.get('id')
                    
                    if not paper_id:
                        continue

                    try:
                        # 상세 정보 가져오기 (GitHub 링크 등은 상세 API에서 더 정확히 나옵니다)
                        detail_res = await client.get(f"{self.detail_url}/{paper_id}")
                        detail_res.raise_for_status()
                        details = detail_res.json()
                        
                        # 상세 데이터에서도 paper 키가 있을 수 있으므로 방어적으로 접근
                        d_paper = details.get('paper', details) 

                        results.append({
                            "id": paper_id,
                            "title": d_paper.get('title') or p.get('title') or "No Title",
                            "summary": d_paper.get('summary') or p.get('summary') or "",
                            "published": (d_paper.get('publishedAt') or p.get('publishedAt') or "N/A")[:10],
                            "upvotes": d_paper.get('upvotes') or p.get('upvotes', 0),
                            # 저자 리스트 추출 (d_paper['authors'] 내부의 name 추출)
                            "authors": ", ".join([a.get('name', 'Unknown') for a in d_paper.get('authors', [])]) if d_paper.get('authors') else "Unknown",
                            "github_url": d_paper.get('github_url'), # 상세 정보 내의 github_url
                            "hf_url": f"https://huggingface.co/papers/{paper_id}",
                            "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf", 
                            "source": "HF"
                        })
                    except Exception as e:
                        print(f"WARNING: 상세 정보 로드 실패 ({paper_id}): {e}")
                        continue

            except Exception as e:
                print(f"ERROR: HF API 호출 중 오류: {e}")
                
        return results