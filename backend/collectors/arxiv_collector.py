import arxiv
import re
import fitz  # PyMuPDF
import httpx
import asyncio
from io import BytesIO

# 전역 클라이언트 인스턴스
arxiv_client = arxiv.Client()

# 1. 키워드 검색용 (기존 로직 유지)
def fetch_arxiv(keyword: str, max_results: int = 5):
    search = arxiv.Search(query=keyword, max_results=max_results)
    return list(arxiv_client.results(search))

# 2. ID 기반 고속 메타데이터 수집 
async def get_metadata_by_id(arxiv_id: str):
    try:
        def fetch():
            search = arxiv.Search(id_list=[arxiv_id])
            res = list(arxiv_client.results(search))
            return res[0] if res else None

        r = await asyncio.to_thread(fetch)
        if r:
            return {
                "comment": r.comment,
                "pdf_url": r.pdf_url
            }
    except Exception as e:
        print(f"DEBUG: ArXiv ID 조회 실패 ({arxiv_id}): {e}")
    return None

# backend/collectors/arxiv_collector.py

async def extract_github_from_pdf(pdf_url: str):
    if not pdf_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()
            
            with fitz.open(stream=BytesIO(response.content), filetype="pdf") as doc:
                search_range = min(3, len(doc)) 
                
                # [수정된 전략] 
                # 앞부분에 숫자가 있든 없든( \d* ) github 주소 패턴을 모두 매칭합니다.
                # (https?://)? 가 있거나 없는 모든 케이스를 고려합니다.
                github_pattern = r'(?:https?://)?\d*[\w\d\-]+\.github\.(?:io|com)/[\w\d\-\./]*'
                
                for i in range(search_range):
                    text = doc[i].get_text()
                    matches = re.finditer(github_pattern, text)
                    for match in matches:
                        raw_url = match.group(0).strip().rstrip(').,/')
                        
                        # [핵심: 1 제거 로직]
                        # 1. 프로토콜(http)이 있다면 그 뒤의 숫자를 제거
                        # 2. 프로토콜이 없다면 문자열 맨 앞의 숫자를 제거
                        # 예: 1speechbrain.github.io -> speechbrain.github.io
                        # 예: https://1speechbrain.github.io -> https://speechbrain.github.io
                        
                        # 프로토콜 분리 처리
                        if raw_url.startswith('http'):
                            clean_url = re.sub(r'(https?://)\d+', r'\1', raw_url)
                        else:
                            clean_url = re.sub(r'^\d+', '', raw_url)
                        
                        # 최종적으로 http가 없으면 붙여줌
                        if not clean_url.startswith('http'):
                            clean_url = 'https://' + clean_url
                        
                        # speechbrain.github.io 처럼 유효한 주소 형태인지 확인
                        if "github" in clean_url.lower():
                            return clean_url
                            
    except Exception as e:
        print(f"DEBUG: PDF 스캔 실패 ({pdf_url}): {e}")
    return None

# 4. 코멘트 내 GitHub 링크 추출
def extract_from_comment(comment_text: str):
    if not comment_text:
        return None
    match = re.search(r'https?://github\.com/[\w\-/]+', comment_text)
    return match.group(0).strip('.') if match else None