import sqlite3
import chromadb
import os
from rapidfuzz import process, fuzz

class StorageManager:
    def __init__(self, embedder=None):
        self.db_dir = "backend/data"
        if not os.path.exists(self.db_dir): os.makedirs(self.db_dir)

        self.sqlite_path = os.path.join(self.db_dir, "metadata.db")
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self._init_sqlite()
        
        self.chroma = chromadb.PersistentClient(path=os.path.join(self.db_dir, "chroma_db"))
        self.collection = self.chroma.get_or_create_collection("research_assets")
        self.embedder = embedder
    # DB 생성
    def _init_sqlite(self):
        """10개 컬럼을 가진 메인 테이블과 FTS5 검색 엔진을 초기화합니다."""
        
        # 1. 메인 테이블 생성 (기존과 동일)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS papers 
            (
                id TEXT PRIMARY KEY, 
                title TEXT, 
                summary TEXT, 
                authors TEXT, 
                pdf_url TEXT, 
                github_url TEXT, 
                hf_url TEXT, 
                published TEXT,
                source TEXT, 
                upvotes INTEGER DEFAULT 0
            )
        """)

        # 2. [추가] FTS5 검색 전용 가상 테이블 생성 (형태소 분석 및 인덱싱)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                id UNINDEXED, -- id는 검색어가 아니므로 인덱싱 제외
                title, 
                summary, 
                authors
            )
        """)

        # 3. [추가] 자동 동기화 트리거 (메인 테이블에 데이터가 들어오면 FTS에도 자동 삽입)
        self.conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS papers_after_insert AFTER INSERT ON papers 
            BEGIN
                INSERT INTO papers_fts(id, title, summary, authors) 
                VALUES (new.id, new.title, new.summary, new.authors);
            END;

            CREATE TRIGGER IF NOT EXISTS papers_after_update AFTER UPDATE ON papers 
            BEGIN
                DELETE FROM papers_fts WHERE id = old.id;
                INSERT INTO papers_fts(id, title, summary, authors) 
                VALUES (new.id, new.title, new.summary, new.authors);
            END;

            CREATE TRIGGER IF NOT EXISTS papers_after_delete AFTER DELETE ON papers 
            BEGIN
                DELETE FROM papers_fts WHERE id = old.id;
            END;
        """)
        self.conn.commit()

    def save_all(self, data, vector): # 'vector' 인자를 명시적으로 추가
        """Linker에서 정리된 데이터와 임베딩 벡터를 함께 저장"""
        sql = "INSERT OR REPLACE INTO papers VALUES (?,?,?,?,?,?,?,?,?,?)"
        self.conn.execute(sql, (
            data['id'], 
            data['title'], 
            data['summary'], 
            data.get('authors', ""),
            data['pdf_url'], 
            data.get('github_url'), 
            data.get('hf_url'),
            data['published'], 
            data['source'], 
            data.get('upvotes', 0)
        ))
        self.conn.commit()
        
        # 전달받은 vector를 사용하여 ChromaDB에 저장
        self.collection.upsert(
            ids=[data['id']], 
            embeddings=[vector], 
            metadatas=[{"title": data['title']}]
        )
        
    # db 초기화
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

    def unified_search(self, query: str, mode: str):
        """FTS5의 강력한 MATCH 쿼리를 활용한 하이브리드 검색"""
        results = []
        try:
            if mode in ["통합 검색", "키워드(Keyword)", "제목(Title)"]:
                
                # 검색어 전처리: FTS5 문법 오류 방지를 위해 특수문자 제거 후 띄어쓰기 기준으로 AND 검색
                # 예: "An Image is" -> '"An" AND "Image" AND "is"'
                clean_terms = [t.replace('"', '').replace("'", "") for t in query.split()]
                fts_query = " AND ".join([f'"{term}"' for term in clean_terms if term])

                # 메인 테이블과 FTS 테이블을 조인하여 결과 반환
                # ORDER BY rank : FTS5 내장 기능으로, 연관도(BM25)가 높을수록 상위에 노출
                sql = """
                    SELECT p.* 
                    FROM papers p
                    JOIN papers_fts f ON p.id = f.id
                    WHERE papers_fts MATCH ?
                    ORDER BY f.rank 
                    LIMIT 50
                """
                
                rows = self.conn.execute(sql, (fts_query,)).fetchall()
                
                for row in rows:
                    results.append({
                        "id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "authors": row[3],
                        "pdf_url": row[4],
                        "github_url": row[5],
                        "hf_url": row[6],
                        "published": row[7],
                        "source": row[8],
                        "upvotes": row[9]
                    })
                    
            elif mode == "AI 시맨틱 검색":
                # 기존 벡터 검색 로직 유지
                pass
                
        except Exception as e:
            print(f"FTS5 DB 검색 중 오류 발생: {e}")

        return results

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