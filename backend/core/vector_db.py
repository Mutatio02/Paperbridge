import sqlite3
import chromadb
import os
from rapidfuzz import process, fuzz

class StorageManager:
    def __init__(self, embedder=None):
        # 1. 경로 설정
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
        
        # 4. 시맨틱 검색을 위한 임베더 (외부에서 주입받음)
        self.embedder = embedder

    def _init_sqlite(self):
        """테이블 초기화: authors 컬럼을 추가하여 통합 검색 대응"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS papers 
            (id TEXT PRIMARY KEY, title TEXT, summary TEXT, authors TEXT, 
             pdf_url TEXT, github_url TEXT, hf_url TEXT, published TEXT)
        """)
        self.conn.commit()

    def reset_db(self):
        """데이터 저장소 완전 초기화"""
        print("데이터 저장소 초기화를 시작합니다...")
        try:
            self.conn.execute("DROP TABLE IF EXISTS papers")
            self._init_sqlite()
            self.chroma.delete_collection("research_assets")
            self.collection = self.chroma.get_or_create_collection("research_assets")
            print("모든 데이터 저장소가 성공적으로 비워졌습니다.")
        except Exception as e:
            print(f"초기화 중 오류 발생: {e}")

    # --- 저장 로직 ---
    def save_all(self, paper, vector, github_url, hf_url):
        """SQLite와 ChromaDB에 멀티모달 자산 동시 저장"""
        # SQLite: authors 정보 포함 (paper 객체에 authors 필드가 있다고 가정)
        authors_str = getattr(paper, 'authors', "")
        self.conn.execute("INSERT OR REPLACE INTO papers VALUES (?,?,?,?,?,?,?,?)",
            (paper.id, paper.title, paper.summary, authors_str, 
             paper.pdf_url, github_url, hf_url, paper.published))
        self.conn.commit()
        
        # ChromaDB: 제목 기반 메타데이터와 함께 벡터 저장
        self.collection.upsert(ids=[paper.id], embeddings=[vector], metadatas=[{"title": paper.title}])

    # --- 검색 핵심 로직 ---
    def unified_search(self, query, mode):
        """사용자가 선택한 모드에 따른 전략적 검색 수행"""
        
        # 1. 통합 검색: 모든 필드를 아우르는 높은 재현율(Recall)
        if mode == "통합 검색":
            sql = "SELECT * FROM papers WHERE id LIKE ? OR title LIKE ? OR summary LIKE ? OR authors LIKE ?"
            term = f"%{query}%"
            return self._execute_and_format(sql, (term, term, term, term))

        # 2. 제목 검색: RapidFuzz를 이용한 유연한 매칭 (Learner/Learners 이슈 해결)
        elif mode == "제목(Title)":
            return self.search_papers_fuzzy(query, threshold=75)

        # 3. 키워드 검색: 핵심 주제 중심 매칭
        elif mode == "키워드(Keyword)":
            sql = "SELECT * FROM papers WHERE title LIKE ? OR summary LIKE ?"
            term = f"%{query}%"
            return self._execute_and_format(sql, (term, term))

        # 4. 분야 검색: ArXiv 카테고리 태그 필터링
        elif mode == "분야(Subject)":
            category_code = query.split(" ")[0] # 예: "cs.CL"
            sql = "SELECT * FROM papers WHERE summary LIKE ?"
            term = f"%{category_code}%"
            return self._execute_and_format(sql, (term,))

        # 5. AI 시맨틱 검색: 임베딩 기반 의미 추출
        elif mode == "AI 시맨틱 검색" and self.embedder:
            query_vector = self.embedder.get_embedding(query)
            paper_ids = self.search_similar_ids(query_vector)
            return self.get_papers_by_ids(paper_ids)

        return []

    def search_papers_fuzzy(self, keyword: str, limit=5, threshold=70):
        """RapidFuzz를 활용한 철자 보정 검색"""
        cursor = self.conn.execute("SELECT id, title FROM papers")
        all_papers = cursor.fetchall()
        if not all_papers: return []

        id_map = {title: pid for pid, title in all_papers}
        titles = list(id_map.keys())

        # fuzz.WRatio를 사용하여 문장 구조 변화에 대응
        matches = process.extract(keyword, titles, scorer=fuzz.WRatio, limit=limit)
        fuzzy_ids = [id_map[title] for title, score, index in matches if score >= threshold]
        
        return self.get_papers_by_ids(fuzzy_ids)

    # --- 유틸리티 메서드 ---
    def search_similar_ids(self, query_vector, n=5):
        res = self.collection.query(query_embeddings=[query_vector], n_results=n)
        return res['ids'][0]

    def get_papers_by_ids(self, paper_ids: list):
        if not paper_ids: return []
        placeholders = ','.join(['?'] * len(paper_ids))
        query = f"SELECT * FROM papers WHERE id IN ({placeholders})"
        return self._execute_and_format(query, paper_ids)

    def _execute_and_format(self, sql, params):
        """SQL 실행 결과를 딕셔너리 리스트로 변환 (Frontend 호환성)"""
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                "id": r[0], "title": r[1], "summary": r[2], "authors": r[3],
                "pdf_url": r[4], "github_url": r[5], "hf_url": r[6], "published": r[7]
            } for r in rows
        ]