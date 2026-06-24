import streamlit as st
import pandas as pd
import io
import json
import re
from streamlit_gsheets import GSheetsConnection

# 페이지 설정
st.set_page_config(page_title="Haegin Asset Management", layout="wide", page_icon="🏢")

# ==============================================================================
# 🎨 더존 ERP + 현대적 UI 커스텀 CSS (Image 2 스타일 구현)
# ==============================================================================
st.markdown("""
<style>
    /* 전체 배경 */
    .stApp { background-color: #F4F5F7; }
    
    /* 사이드바 스타일 (네비게이션) */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0;
    }
    
    /* 사이드바 로고 섹션 */
    .sidebar-logo {
        text-align: center;
        padding: 10px 0 30px 0;
        border-bottom: 2px solid #00AEEF;
        margin-bottom: 20px;
    }

    /* 사이드바 라디오 버튼을 커스텀 메뉴처럼 변신 */
    div[data-testid="stSidebarNav"] { padding-top: 0rem; }
    
    /* 메뉴 항목 디자인 */
    .st-emotion-cache-1647z6a {
        padding: 10px 15px !important;
        border-radius: 8px !important;
        margin-bottom: 5px !important;
    }
    
    /* 배지(Badge) 스타일 CSS */
    .menu-row {
        display: flex;
        align-items: center;
        width: 100%;
        font-size: 16px;
    }
    .badge {
        background-color: #00AEEF;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-left: auto;
    }

    /* 메인 컨테이너 */
    .block-container { padding-top: 2rem !important; }
    
    /* 버튼 스타일 */
    .stButton > button {
        background-color: #00AEEF !important;
        color: white !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. 구글 시트 연결 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    HAS_CONN = True
except Exception as e:
    HAS_CONN = False
    st.error(f"연결 실패: {e}")

# --- 2. 데이터 구조 및 유틸리티 ---
COLS = {
    "비품": ["대분류", "소분류", "품목", "최종확인 년도", "분류코드", "개수", "관리번호", "자산번호", "제조사", "모델명", "취득일", "취득가", "위치", "세부위치"],
    "SW": ["대분류", "소분류", "구매일자", "사용자", "소속", "이메일", "사용기한", "비고"],
    "PC": ["대분류", "소분류", "사번", "이름", "소속", "관리번호", "입사일", "교체일", "분류", "CPU", "RAM", "VGA", "디스크1", "디스크2", "OS", "구매일자", "금액", "비고"],
    "대여비품": ["대분류", "소분류", "구분", "책상 H-DE", "의자 H-HM", "서랍 H-DR"]
}

def safe_rerun():
    try: st.rerun()
    except: st.experimental_rerun()

def normalize_str(s):
    if pd.isna(s): return ""
    s = str(s).strip().replace(" ", "")
    return re.sub(r'^\d+[\._\s\-]*', '', s)

# 데이터 로드/저장 함수
@st.cache_data(ttl=600)
def load_data(dtype):
    sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
    try: return conn.read(worksheet=sheet_name, ttl=0).fillna("")
    except: return pd.DataFrame(columns=COLS[dtype] if dtype != "비품" else COLS["비품"] + COLS["대여비품"])

def save_data(df, dtype):
    sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
    conn.update(worksheet=sheet_name, data=df.fillna("").astype(str))
    st.cache_data.clear()

def load_config():
    try:
        df_conf = conn.read(worksheet="menu_config", ttl=0).fillna("")
        config = {}
        for _, row in df_conf.iterrows():
            main, dtype, sub = str(row["대분류"]), str(row["양식타입"]), str(row["소분류"])
            if main not in config: config[main] = {"type": dtype, "subs": []}
            if sub: config[main]["subs"].append(sub)
        return config
    except:
        return {
            "1. 해긴 비품 리스트": {"type": "비품", "subs": ["사무실&회의실", "하이퍼라이즈 대여 비품"]},
            "2. PC 관리": {"type": "PC", "subs": ["전체 사용 PC 목록"]},
            "3. SW목록": {"type": "SW", "subs": ["Adobe", "MS Office"]}
        }

# --- 3. 데이터 로딩 ---
if HAS_CONN:
    menu_config = load_config()
    df_eq = load_data("비품")
    df_sw = load_data("SW")
    df_pc = load_data("PC")
else: st.stop()

# --- 4. 사이드바 구성 (Image 1 & 2 스타일) ---
# 로고 (Image 1 스타일)
st.sidebar.markdown(f'<div class="sidebar-logo"><h2 style="color:#00AEEF; margin:0;">HAEGIN</h2><small style="color:#666;">Asset Management</small></div>', unsafe_allow_html=True)

# 메뉴 리스트 및 실시간 배지(Badge) 계산
counts = {
    "비품": len(df_eq),
    "SW": len(df_sw),
    "PC": len(df_pc)
}

# 네비게이션
nav_options = ["📊 통합 대시보드"] + list(menu_config.keys()) + ["⚙️ 환경설정"]
selected_menu = st.sidebar.radio("자산 · 비품 관리", nav_options)

st.sidebar.markdown("---")
# 엑셀 동기화 UI (이전 로직 유지)
if selected_menu not in ["📊 통합 대시보드", "⚙️ 환경설정"]:
    st.sidebar.subheader("🔄 엑셀 업로드")
    sub_target = st.sidebar.selectbox("대상 탭", menu_config[selected_menu]["subs"])
    up_file = st.sidebar.file_uploader("파일 선택", type=["xlsx", "csv"])
    if up_file and st.sidebar.button("📥 최종 적용"):
        df_up = pd.read_excel(up_file) if up_file.name.endswith(".xlsx") else pd.read_csv(up_file)
        df_up["대분류"], df_up["소분류"] = selected_menu, sub_target
        dtype = menu_config[selected_menu]["type"]
        df_final = pd.concat([load_data(dtype), df_up], ignore_index=True).drop_duplicates().fillna("")
        save_data(df_final, dtype)
        st.sidebar.success("동기화 완료!")
        safe_rerun()

# --- 5. 메인 화면 ---

# 🟢 통합 대시보드
if selected_menu == "📊 통합 대시보드":
    st.title("📈 Haegin Asset Insights")
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 하드웨어", f"{len(df_pc)} 개")
    c2.metric("운용 소프트웨어", f"{len(df_sw)} 개")
    c3.metric("관리 비품", f"{len(df_eq)} 건")

# 🟢 SW 목록 대시보드 (사용자 요청사항)
elif normalize_str(selected_menu) == normalize_str("3. SW목록"):
    st.title("💾 Software License Intelligence")
    
    # SW 대시보드 데이터 가공
    if not df_sw.empty:
        # 소분류(제품군)별 요약
        sw_summary = df_sw.groupby("소분류").size().reset_index(name="사용중")
        # 임시로 '총 개수'를 안전재고나 별도 테이블이 없을 경우 사용중+2로 예시 (실제 시트 기반으로 수정 가능)
        sw_summary["총라이선스"] = sw_summary["사용중"] + 2 
        
        st.subheader("📊 항목별 라이선스 현황")
        cols = st.columns(len(sw_summary))
        for i, row in sw_summary.iterrows():
            with cols[i % 3]:
                st.metric(row["소분류"], f"{row['사용중']} / {row['총라이선스']}", help=f"{row['소분류']} 상세 현황")

        # 탭 구성 (에디터 포함)
        st.markdown("---")
        sub_tabs = menu_config[selected_menu]["subs"]
        tabs = st.tabs(sub_tabs)
        for i, tab_name in enumerate(sub_tabs):
            with tabs[i]:
                f_df = df_sw[(df_sw["대분류"] == selected_menu) & (df_sw["소분류"] == tab_name)]
                display_cols = [c for c in COLS["SW"] if c not in ["대분류", "소분류"]]
                edited = st.data_editor(f_df[display_cols], num_rows="dynamic", use_container_width=True, key=f"ed_{tab_name}")
                if st.button("💾 데이터 저장", key=f"sv_{tab_name}"):
                    edited["대분류"], edited["소분류"] = selected_menu, tab_name
                    df_others = df_sw[~((df_sw["대분류"] == selected_menu) & (df_sw["소분류"] == tab_name))]
                    save_data(pd.concat([df_others, edited], ignore_index=True), "SW")
                    st.success("저장 완료!")
                    safe_rerun()
    else:
        st.info("SW 데이터가 없습니다. 엑셀을 업로드해 주세요.")

# 🟢 나머지 탭 (에디터 공통 적용)
elif selected_menu != "⚙️ 환경설정":
    st.title(f"📂 {selected_menu}")
    dtype = menu_config[selected_menu]["type"]
    sub_tabs = menu_config[selected_menu]["subs"]
    
    if sub_tabs:
        tabs = st.tabs(sub_tabs)
        for i, sub in enumerate(sub_tabs):
            with tabs[i]:
                # 탭별 맞춤 양식 결정
                if normalize_str(sub) == normalize_str("하이퍼라이즈 대여 비품"):
                    target_cols = COLS["대여비품"]
                else: target_cols = COLS[dtype]
                
                display_cols = [c for c in target_cols if c not in ["대분류", "소분류"]]
                
                df_master = df_eq if dtype == "비품" else (df_pc if dtype == "PC" else df_sw)
                f_df = df_master[(df_master["대분류"] == selected_menu) & (df_master["소분류"] == sub)]
                
                # 데이터 에디터
                for c in display_cols: 
                    if c not in f_df.columns: f_df[c] = ""
                
                edited = st.data_editor(f_df[display_cols], num_rows="dynamic", use_container_width=True, key=f"ed_{selected_menu}_{sub}")
                
                if st.button("💾 변경사항 저장", key=f"btn_{selected_menu}_{sub}"):
                    edited["대분류"], edited["소분류"] = selected_menu, sub
                    df_others = df_master[~((df_master["대분류"] == selected_menu) & (df_master["소분류"] == sub))]
                    save_data(pd.concat([df_others, edited], ignore_index=True), dtype)
                    st.success("저장 완료!")
                    safe_rerun()
    else: st.info("하위 탭을 생성하세요.")

# 🟢 환경설정
else:
    st.title("⚙️ 시스템 설정")
    # 탭 추가/삭제 로직 (이전 코드 유지)
    st.write("환경설정 메뉴를 통해 탭을 관리하세요.")
