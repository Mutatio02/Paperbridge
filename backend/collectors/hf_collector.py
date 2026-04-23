import os
from huggingface_hub import HfApi
from dotenv import load_dotenv

load_dotenv()
# 토큰이 없어도 작동은 하지만, .env에 HF_TOKEN을 넣으면 더 안정적.
api = HfApi(token=os.getenv("HF_TOKEN"))

def fetch_hf_by_arxiv_id(arxiv_id):
    try:
        # ArXiv ID 태그로 모델 검색 (가장 정확한 방법)
        # direction=-1 대신 sort="downloads"만 사용해도 충분.
        # 최신 버전에서는 direction 인자가 없는 경우가 많다.
        models = api.list_models(
            filter=f"arxiv:{arxiv_id}", 
            sort="downloads", 
            limit=1  # 어차피 하나만 필요하므로 제한.
        )
        model_list = list(models)
        
        if model_list:
            return f"https://huggingface.co/{model_list[0].id}"
    except Exception as e:
        print(f"HF 수집 중 오류: {e}")
    return None