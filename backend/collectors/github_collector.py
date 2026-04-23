import os
import re
from github import Github
from dotenv import load_dotenv

load_dotenv()
g = Github(os.getenv("GITHUB_TOKEN"))

def fetch_github_link(title: str):
    try:
        # 제목에서 특수문자 제거 및 핵심 단어 추출
        clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
        query = " ".join(clean_title.split()[:6]) # 앞 6단어만 사용
        
        # 이름과 설명에서 검색하여 Star 순으로 정렬
        repos = g.search_repositories(query=f"{query} in:name,description", sort="stars", order="desc")
        if repos.totalCount > 0:
            return repos[0].html_url
    except:
        return None
    return None