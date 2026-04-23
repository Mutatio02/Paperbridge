import sqlite3
import chromadb
import os

class StorageManager:
    def __init__(self):
        # 1. 경로 설정 (폴더가 없으면 에러가 나므로 체크 로직 포함)
        self.db_dir = "backend/data"
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

        # 2. SQLite 설정
        self.sqlite_path = os.path.join(self.db_dir, "metadata.db")
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self._init_sqlite()
        
        # 3. ChromaDB 설정
        self.chroma_path = os.path.join(self.db_dir, "chroma_db")
        self.chroma = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.chroma.get_or_create_collection("research_assets")

    def _init_sqlite(self):
        """테이블 초기화 및 생성"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS papers 
            (id TEXT PRIMARY KEY, title TEXT, summary TEXT, pdf_url TEXT, github_url TEXT, hf_url TEXT, published TEXT)
        """)
        self.conn.commit()
    
    def reset_db(self):
        """기존 데이터를 모두 삭제하고 초기화합니다."""
        print("DB 초기화를 시작합니다...")
        
        # 1. SQLite 초기화: 테이블 삭제 후 다시 생성
        try:
            self.conn.execute("DROP TABLE IF EXISTS papers")
            self._init_sqlite()
            print("SQLite 테이블 초기화 완료.")
        except Exception as e:
            print(f"SQLite 초기화 실패: {e}")

        # 2. ChromaDB 초기화: 컬렉션 삭제 후 다시 생성
        try:
            self.chroma.delete_collection("research_assets")
            self.collection = self.chroma.get_or_create_collection("research_assets")
            print("ChromaDB 컬렉션 초기화 완료.")
        except Exception as e:
            # 컬렉션이 이미 없는 경우를 대비
            self.collection = self.chroma.get_or_create_collection("research_assets")
            print(f"ChromaDB 알림: {e}")
            
        print("모든 데이터 저장소가 비워졌습니다.")

    def save_all(self, paper, vector, github_url, hf_url):
        # SQLite 저장 (기존 데이터가 있으면 덮어씌움)
        self.conn.execute("INSERT OR REPLACE INTO papers VALUES (?,?,?,?,?,?,?)",
            (paper.id, paper.title, paper.summary, paper.pdf_url, github_url, hf_url, paper.published))
        self.conn.commit()
        # ChromaDB 저장
        self.collection.upsert(ids=[paper.id], embeddings=[vector], metadatas=[{"title": paper.title}])

    def search_similar_ids(self, query_vector, n=5):
        res = self.collection.query(query_embeddings=[query_vector], n_results=n)
        return res['ids'][0]

    def get_papers_by_ids(self, paper_ids):
        if not paper_ids:
            return []
        placeholders = ', '.join(['?'] * len(paper_ids))
        cursor = self.conn.execute(f"SELECT * FROM papers WHERE id IN ({placeholders})", paper_ids)
        return cursor.fetchall()