import arxiv
import re
import fitz  
import requests
from io import BytesIO
from backend.models.paper import PaperModel

def fetch_arxiv(keyword: str, max_results: int = 5):
    client = arxiv.Client()
    search = arxiv.Search(query=keyword, max_results=max_results)
    
    results = []
    for r in client.results(search):
        # 1. 댓글(comment)에서 링크 먼저 추출 시도
        github_from_comment = extract_from_comment(r.comment)
        
        paper = PaperModel(
            id=r.entry_id.split('/')[-1],
            title=r.title,
            summary=r.summary,
            pdf_url=r.pdf_url,
            published=str(r.published.date())
        )
        # 임시로 comment에서 찾은 링크를 객체에 붙여서 전달 (나중에 linker에서 사용)
        paper.temp_github_from_comment = github_from_comment 
        results.append(paper)
    return results

def extract_from_comment(comment_text):
    if not comment_text:
        return None
    match = re.search(r'https?://github\.com/[\w\-/]+', comment_text)
    return match.group(0).strip('.') if match else None

def extract_github_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=10)
        with fitz.open(stream=BytesIO(response.content), filetype="pdf") as doc:
            search_range = min(3, len(doc)) 
            
            # 정규표현식 확장: github.com 뿐만 아니라 github.io 도 포함
            # 1. github.com/user/repo 형태
            # 2. user.github.io/repo 혹은 project.github.io 형태 모두 잡음
            github_pattern = r'(https?://)?([\w\d\-]+\.github\.io/[\w\d\-\./]*|github\.com/[\w\d\-\./]+)'
            
            for i in range(search_range):
                text = doc[i].get_text()
                matches = re.finditer(github_pattern, text)
                for match in matches:
                    url = match.group(0).strip()
                    # 끝에 붙은 마침표, 쉼표, 괄호 등 제거
                    url = url.rstrip(').,/')
                    
                    if not url.startswith('http'):
                        url = 'https://' + url
                    
                    # 유효한 주소인지 간단히 확인 후 즉시 반환
                    if "github" in url:
                        return url
    except Exception as e:
        print(f"PDF 스캔 실패: {e}")
    return None