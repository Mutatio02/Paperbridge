from pydantic import BaseModel
from typing import Optional

class PaperModel(BaseModel):
    id: str                 
    title: str              
    summary: str            
    authors: Optional[str] = ""  
    # [수정] 필수 필드에서 선택 필드로 변경
    pdf_url: Optional[str] = "https://arxiv.org" 
    published: str          
    github_url: Optional[str] = None 
    hf_url: Optional[str] = None     
    source: str = "ArXiv"   
    upvotes: int = 0
    # [추가된 필드] ArXiv 수집 과정에서 임시로 GitHub 주소를 담아두는 용도
    temp_github_from_comment: Optional[str] = None