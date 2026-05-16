import httpx
import os

# 만약 GitHub 토큰이 없다면 빈 문자열이나 None으로 두세요.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") 

async def fetch_github_link(title: str):
    # 비동기 사용해야 합니다.
    async with httpx.AsyncClient() as client:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            # 논문 제목을 그대로 검색하면 결과가 잘 안나올 수 있으니
            # "official implementation" 같은 키워드를 붙여도 좋습니다.
            query = f"{title} in:readme,name,description"
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
            
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            if data.get("items") and len(data["items"]) > 0:
                # 가장 별이 많은(인기 있는) 저장소의 URL 반환
                return data["items"][0]["html_url"]
                
        except Exception as e:
            print(f"DEBUG: GitHub API 검색 실패 ({title[:20]}...): {e}")
            
    return None