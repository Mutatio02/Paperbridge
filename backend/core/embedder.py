import torch
from sentence_transformers import SentenceTransformer

class PaperEmbedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # GPU load
        self.model = SentenceTransformer("all-MiniLM-L6-v2").to(self.device)

    def encode(self, text: str):
        return self.model.encode(text).tolist()