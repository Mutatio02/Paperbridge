import streamlit as st
import requests
import pandas as pd

# 1. 페이지 설정 및 디자인 (Figma 스타일 테마)
st.set_page_config(page_title="Paper-Bridge Dashboard", page_icon="🌉", layout="wide")

# Custom CSS: 메트릭 카드 및 레이아웃 커스텀
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 백엔드 통신 및 로직 함수
BACKEND_URL = "http://localhost:8000"

def get_data(query, mode):
    """검색 모드에 따라 백엔드에서 데이터를 가져오고, 없으면 자동 수집을 트리거합니다."""
    try:
        # 1. 백엔드 검색 요청 (모드 포함)
        response = requests.get(f"{BACKEND_URL}/search", params={"query": query, "mode": mode}, timeout=10)
        data = response.json()

        # 2. 결과가 존재하면 즉시 반환
        if isinstance(data, list) and len(data) > 0:
            return data

        # 3. 결과가 없는 경우(빈 리스트) 자동 동기화 시도
        # AI 시맨틱 검색이나 분야 검색은 로컬 데이터 기반이므로, 통합/제목 검색 시에만 자동 수집 권장
        if mode in ["통합 검색", "제목(Title)", "키워드(Keyword)"]:
            st.info(f"🔍 '{query}' 관련 로컬 데이터가 없습니다. 실시간 수집 및 분석을 시작합니다...")
            if sync_new_data(query):
                # 수집 성공 후 다시 검색
                response = requests.get(f"{BACKEND_URL}/search", params={"query": query, "mode": mode})
                return response.json()
        
        return []
    except Exception as e:
        st.error(f"Backend Connection Error: {e}")
        return []

def sync_new_data(keyword):
    """RTX 5070 엔진을 가동하여 ArXiv, GitHub, HF 데이터를 수집합니다."""
    with st.spinner(f"🚀 RTX 5070 가동 중: '{keyword}' 관련 최신 논문 및 코드 수집 중..."):
        try:
            res = requests.post(f"{BACKEND_URL}/sync", params={"keyword": keyword}, timeout=100)
            if res.status_code == 200:
                st.success(f"✅ '{keyword}' 데이터 동기화 완료!")
                return True
            return False
        except Exception as e:
            st.error(f"동기화 중 오류 발생: {e}")
            return False

def safe_count(data_list, key):
    """리스트 내 딕셔너리 요소의 특정 키 존재 여부를 안전하게 카운트합니다."""
    return sum(1 for item in data_list if isinstance(item, dict) and item.get(key))

# 3. Header 영역
st.title("🌉 AI Research Integration Dashboard")
st.caption("Explore papers from arXiv, code from GitHub, and models from Hugging Face in one unified interface")
st.divider()

# --- 4. Search & Filter 제어 영역 (고정 레이아웃) ---
# 레이아웃 비율을 명확히 고정합니다.
col_mode, col_input, col_btn = st.columns([1.2, 3, 0.8])

with col_mode:
    # 검색 모드 선택 (라벨을 아예 없애거나 공백으로 통일)
    search_mode = st.selectbox(
        "Mode", 
        ["통합 검색", "제목(Title)", "키워드(Keyword)", "AI 시맨틱 검색", "분야(Subject)"],
        label_visibility="collapsed" # 라벨을 숨겨서 수직 위치를 col_input과 맞춤
    )

# 이 컨테이너가 입력창의 위치를 고정하는 '앵커' 역할을 합니다.
input_container = col_input.container()

with input_container:
    if search_mode == "분야(Subject)":
        # 분야 선택 selectbox
        query = st.selectbox(
            "Select Subject", # 내부 관리를 위한 라벨
            ["cs.CL (NLP)", "cs.LG (ML)", "cs.CV (Vision)", "cs.AI (AI)"],
            label_visibility="collapsed", # 위와 동일하게 collapsed 적용
            key="subject_select" # 위젯 상태 유지를 위한 키값 부여
        )
    else:
        # 일반 텍스트 input
        query = st.text_input(
            label="Search Query",
            placeholder=f"{search_mode} 모드로 검색어를 입력하세요...",
            label_visibility="collapsed", # 위와 동일하게 collapsed 적용
            key="text_search" # 위젯 상태 유지를 위한 키값 부여
        )

with col_btn:
    # 버튼 높이를 입력창과 맞추기 위해 상단 여백 조절이 필요할 수 있음
    search_clicked = st.button("Search 🔍", use_container_width=True, type="primary")
# 데이터 로드 로직
results = []
if search_clicked and query:
    results = get_data(query, search_mode)
elif query and not search_clicked:
    # 버튼을 누르지 않아도 기본적으로 query가 있으면 기존 데이터를 보여줄 수 있음 (선택 사항)
    pass

# 5. 메트릭 카드 (대시보드 상단 요약)
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("arXiv Papers", len(results))
with m2:
    st.metric("GitHub Repos", safe_count(results, 'github_url'))
with m3:
    st.metric("HF Models", safe_count(results, 'hf_url'))

st.divider()

# 6. 3-Panel Layout (메인 콘텐츠 영역)
panel_arxiv, panel_github, panel_hf = st.columns(3)

with panel_arxiv:
    st.subheader("📄 arXiv Papers")
    if not results:
        st.write("검색 결과가 없습니다.")
    for p in results:
        if isinstance(p, dict):
            with st.container(border=True):
                st.markdown(f"**{p.get('title', 'No Title')}**")
                st.caption(f"📅 {p.get('published', 'N/A')} | 🆔 {p.get('id', 'N/A')}")
                with st.expander("Abstract 보기"):
                    st.write(p.get('summary', 'No Summary'))
                if p.get('pdf_url'):
                    st.link_button("PDF Open", p['pdf_url'], use_container_width=True)

with panel_github:
    st.subheader("💻 GitHub Repos")
    code_results = [r for r in results if isinstance(r, dict) and r.get('github_url')]
    if not code_results:
        st.write("연결된 코드가 없습니다.")
    for p in code_results:
        with st.container(border=True):
            st.info(f"🔗 Linked to: {p.get('title', '')[:50]}...")
            st.link_button("Go to Repository", p['github_url'], use_container_width=True)

with panel_hf:
    st.subheader("🤗 Hugging Face")
    hf_results = [r for r in results if isinstance(r, dict) and r.get('hf_url')]
    if not hf_results:
        st.write("연결된 모델이 없습니다.")
    for p in hf_results:
        with st.container(border=True):
            st.warning(f"🤖 Model/Dataset Found")
            st.write(f"Ref: {p.get('title', '')[:50]}...")
            st.link_button("View on Hugging Face", p['hf_url'], use_container_width=True)

# 7. Footer
st.markdown("---")
st.caption(f"© 2026 Sungjun An | UTL Lab Intern Project | Powered by NVIDIA RTX 5070")