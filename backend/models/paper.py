from pydantic import BaseModel
from typing import Optional
# 논문 기본 정보
class PaperModel(BaseModel):
    id: str             
    title: str            
    summary: str          
    pdf_url: str           
    published: str         
    github_url: Optional[str] = None  
    hf_url: Optional[str] = None      
    temp_github_from_comment: Optional[str] = None