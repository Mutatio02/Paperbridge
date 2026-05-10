from pydantic import BaseModel
from typing import Optional

class AssetModel(BaseModel):
    paper_id: str           # 연결된 논문 ID
    github_url: Optional[str] = None
    hf_url: Optional[str] = None
    stars: int = 0          # GitHub Stars 수
    upvotes: int = 0        # Hugging Face Upvotes 수
    has_code: bool = False  # 코드 존재 여부 (UI 필터용)
    has_model: bool = False # 모델 존재 여부 (UI 필터용)