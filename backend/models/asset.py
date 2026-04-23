from pydantic import BaseModel
from typing import Optional
# 연결된 코드 및 데이터 정보
class AssetModel(BaseModel):
    paper_id: str
    github_url: Optional[str] = None
    hf_url: Optional[str] = None
    stars: int = 0