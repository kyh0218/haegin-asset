import streamlit as st
import pandas as pd
import io
import json
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="해긴 자산/비품 통합 관리 ERP", layout="wide")

# ==============================================================================
# 🎨 더존 ERP 스타일 커스텀 CSS 주입
# ==============================================================================
st.markdown("""
<style>
    /* 전체 배경 및 폰트 미세조정 */
    .stApp {
        background-color: #F4F5F7;
    }
    
    /* 좌측 사이드바 (더존 특유의 네이비 블루 컬러) */
    [data-testid="stSidebar"] {
        background-color: #1A365D !important;
        padding-top: 2rem;
    }
    [data-testid="stSidebar"] * {
        color: #F8F9FA !important;
    }
    /* 사이드바 구분선 컬러 변경 */
    [data-testid="stSidebar"] hr {
        border-color: #2D4A77 !important;
    }
    
    /* 상단 여백 최소화 (더 많은 데이터를 한눈에) */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 95% !important;
    }
    
    /* 데이터프레임(표) 스타일링 */
    [data-testid="stDataFrame"] {
        background-color: #FFFFFF;
        border-radius: 8px;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.05);
        padding: 10px;
    }
    
    /* 메인 버튼 스타일 (ERP 테마 컬러 적용) */
    .stButton > button {
        background-color: #0052A4 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 4px !important;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #003B75 !important;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.2);
    }
    
    /* Metric(요약 통계) 카드 디자인 */
    [data-testid="stMetricValue"] {
        color: #1A365D;
        font-weight: 800;
    }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #0052A4;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)


# --- 1. 구글 스프레드시트 커넥션 연결 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    HAS_CONN = True
except Exception as e:
    HAS_CONN = False
    st.error(f"구글 시트 연결 실패. Secrets 설정을 확인하세요. 에러: {e}")

# --- 2. 엑셀 양식 기준 ---
COLS = {
    "비품": ["대분류", "소분류", "품목", "최종확인 년도", "분류코드", "개수", "관리번호", "자산번호", "제조사", "모델명", "취득일", "취득가", "위치", "세부위치"],
    "SW": ["대분류", "소분류", "구매일자", "사용자", "소속", "이메일", "사용기한", "비고"],
    "PC": ["대분류", "소분류", "사번", "이름", "소속", "관리번호", "입사일", "교체일", "분류", "CPU", "RAM", "VGA", "디스크1", "디스크2", "OS", "구매일자", "금액", "비고"],
    "대여비품": ["대분류", "소분류", "구분", "책상 H-DE", "의자 H-HM", "서랍 H-DR"]
}

# --- 3. 유틸리티 및 데이터 입출력 함수 ---
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def normalize_str(s):
    if pd.isna(s): return ""
    s = str(s).strip().replace(" ", "")
    s = re.sub(r'^\d+[\._\s\-]*', '', s)
    return s

def get_expected_cols(main_tab, sub_tab, dtype):
    if normalize_str(sub_tab) == normalize_str("하이퍼라이즈 대여 비품"):
        return COLS["대여비품"]
    return COLS[dtype]

# [구글 시트 연동] 메뉴 설정 불러오기
def load_config():
    default_config = {
        "1. 해긴 비품 리스트": {"type": "비품", "subs": ["사무실&회의실", "휴게실 및 기타", "탕비실&카페테리아", "계절용품", "하이퍼라이즈 대여 비품"]},
        "2. PC 관리": {"type": "PC", "subs": ["전체 사용 PC 목록", "잔여재고", "모니터"]},
        "3. SW목록": {"type": "SW", "subs": ["백신", "Office", "Adobe", "3Ds Max", "VS 2022 pro", "Jetbrains&GitHub", "클로드", "업무용 AI 툴", "기타(구독형)", "기타(영구)", "윈도우", "한글&더존"]},
        "4. 보안모듈": {"type": "SW", "subs": ["보안모듈 통합"]},
        "5. 에셋&플러그인": {"type": "SW", "subs": ["에셋&플러그인 통합"]},
        "6. SW 구매내역": {"type": "SW", "subs": ["구매내역 통합"]}
    }
    if HAS_CONN:
        try:
            df_conf = conn.read(worksheet="menu_config", ttl=600).fillna("")
            if df_conf.empty: return default_config
            config = {}
            for _, row in df_conf.iterrows():
                main = str(row["대분류"]).strip()
                dtype = str(row["양식타입"]).strip()
                sub = str(row["소분류"]).strip()
                if not main: continue
                if main not in config: config[main] = {"type": dtype, "subs": []}
                if sub and sub != "(소분류 없음)" and sub not in config[main]["subs"]:
                    config[main]["subs"].append(sub)
            if "1. 해긴 비품 리스트" in config and "하이퍼라이즈 대여 비품" not in config["1. 해긴 비품 리스트"]["subs"]:
                config["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
            return config
        except: return default_config
    return default_config

# [구글 시트 연동] 메뉴 설정 저장하기
def save_config(config):
    if HAS_CONN:
        rows = []
        for main, info in config.items():
            if not info["subs"]: rows.append({"대분류": main, "양식타입": info["type"], "소분류": ""})
            else:
                for sub in info["subs"]: rows.append({"대분류": main, "양식타입": info["type"], "소분류": sub})
        conn.update(worksheet="menu_config", data=pd.DataFrame(rows))
        st.cache_data.clear() # 💡 저장 즉시 모든 사용자 캐시 폭파 (실시간 갱신)

# 💡 [속도+안정성 핵심] 불러올 때는 10분 캐싱 적용
def load_data(dtype):
    if HAS_CONN:
        try:
            sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
            return conn.read(worksheet=sheet_name, ttl=600).fillna("")
        except: pass
    return pd.DataFrame(columns=COLS[dtype] if dtype != "비품" else COLS["비품"] + COLS["대여비품"])

# 💡 [속도+안정성 핵심] 저장하는 순간 캐시 즉시 비우기
def save_data(df, dtype):
    if HAS_CONN:
        sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
        conn.update(worksheet=sheet_name, data=df.fillna("").astype(str))
        st.cache_data.clear() # 💡 내가 저장하면 나 포함 모든 팀원의 화면이 즉시 최신화됨!

# --- 4. 데이터 세션 바인딩 ---
if HAS_CONN:
    st.session_state.menu_config = load_config()
    st.session_state.df_비품 = load_data("비품")
    st.session_state.df_SW = load_data("SW")
    st.session_state.df_PC = load_data("PC")
else: st.stop()

menus = st.session_state.menu_config
eq_df, sw_df, pc_df = st.session_state.df_비품, st.session_state.df_SW, st.session_state.df_PC

# --- 5. 사이드바 네비게이션 ---
st.sidebar.title("🏢 Haegin Asset ERP")
nav_list = ["📊 ERP 대시보드 (통합)"] + list(menus.keys()) + ["⚙️ 기초 정보 관리 (탭 설정)"]
selected_menu = st.sidebar.radio("메뉴 네비게이션", nav_list)

st.sidebar.markdown("---")

# --- 6. 엑셀 연동 로직 ---
st.sidebar.header("📁 일괄 데이터 동기화")
if selected_menu not in ["📊 ERP 대시보드 (통합)", "⚙️ 기초 정보 관리 (탭 설정)"]:
    sub_list = menus[selected_menu]["subs"] if menus[selected_menu]["subs"] else ["(소분류 없음)"]
    target_sub = st.sidebar.selectbox("🎯 업로드 대상 탭", sub_list)
    target_type = menus[selected_menu]["type"]
    expected_cols = get_expected_cols(selected_menu, target_sub, target_type)
    
    if st.sidebar.button("📝 빈 양식 다운로드"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            pd.DataFrame(columns=[c for c in expected_cols if c not in ["대분류", "소분류"]]).to_excel(writer, index=False, sheet_name='입력양식')
        st.sidebar.download_button("📥 내 PC에 저장", data=buffer.getvalue(), file_name=f"{target_sub}_양식.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    st.sidebar.markdown("---")
    upload_mode = st.sidebar.radio("업로드 방식:", ["현재 탭 덮어쓰기 (교체)", "현재 탭 아래에 추가"])
    uploaded_file = st.sidebar.file_uploader("엑셀 파일 선택", type=["xlsx", "csv"])

    if uploaded_file:
        if st.sidebar.button("📥 시스템에 최종 적용하기", use_container_width=True):
            try:
                df_up = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file, encoding="utf-8-sig")
                df_up["대분류"], df_up["소분류"] = selected_menu, target_sub
                
                for c in expected_cols:
                    if c not in df_up.columns: df_up[c] = ""
                df_up = df_up[expected_cols].fillna("")
                
                df_existing = load_data(target_type)
                if upload_mode == "현재 탭 덮어쓰기 (교체)" and not df_existing.empty and "대분류" in df_existing.columns:
                    df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                                (df_existing['소분류'].apply(normalize_str) == normalize_str(target_sub)))]
                
                df_final = pd.concat([df_existing, df_up], ignore_index=True).fillna("")
                save_data(df_final, target_type)
                st.sidebar.success(f"[{target_sub}] 탭 업데이트 완료!")
                safe_rerun()
            except Exception as e: st.sidebar.error(f"오류: {e}")

# --- 7. 메인 화면 로직 ---

# 🟢 통합 대시보드
if selected_menu == "📊 ERP 대시보드 (통합)":
    st.header("📈 전사 자산/비품 통합 현황")
    
    eq_count = pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').sum() if not eq_df.empty else 0
    eq_val = (pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').fillna(0) * pd.to_numeric(eq_df.get("취득가", pd.Series()), errors='coerce').fillna(0)).sum() if not eq_df.empty else 0
    pc_count = len(pc_df)
    pc_val = pd.to_numeric(pc_df.get("금액", pd.Series()), errors='coerce').sum() if not pc_df.empty else 0
    sw_count = len(sw_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 전체 하드웨어/비품", f"{int(eq_count + pc_count):,.0f} 개")
    col2.metric("💾 운용 중인 SW 라이선스", f"{sw_count:,.0f} 개")
    col3.metric("💰 자산 취득가 총액", f"₩ {int(eq_val + pc_val):,.0f}")
    
    st.markdown("---")
    st.info("💡 **실시간 연동 가동 중:** 다른 담당자가 정보를 수정하면 캐시가 자동 초기화되어 즉시 화면에 반영됩니다.")

# 🟢 탭 관리 (환경설정)
elif selected_menu == "⚙️ 기초 정보 관리 (탭 설정)":
    st.header("⚙️ 기초 정보 설정 (카테고리 관리)")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("대분류 관리")
        with st.form("add_main_form"):
            new_main_name = st.text_input("새 대분류 명칭")
            new_main_type = st.selectbox("적용 템플릿", ["비품", "SW", "PC"])
            if st.form_submit_button("대분류 등록"):
                if new_main_name and new_main_name not in menus:
                    menus[new_main_name] = {"type": new_main_type, "subs": []}
                    save_config(menus)
                    safe_rerun()
        with st.form("del_main_form"):
            del_main_name = st.selectbox("삭제 대상 대분류", list(menus.keys()))
            if st.form_submit_button("선택 삭제"):
                del menus[del_main_name]
                save_config(menus)
                safe_rerun()
    with c2:
        if menus:
            st.subheader("소분류 관리")
            with st.form("add_sub_form"):
                target_main_conf = st.selectbox("상위 대분류 선택", list(menus.keys()))
                new_sub_name = st.text_input("새 소분류 명칭")
                if st.form_submit_button("소분류 등록"):
                    if new_sub_name and new_sub_name not in menus[target_main_conf]["subs"]:
                        menus[target_main_conf]["subs"].append(new_sub_name)
                        save_config(menus)
                        safe_rerun()
            with st.form("del_sub_form"):
                del_target_main = st.selectbox("상위 대분류", list(menus.keys()), key="dsm")
                if menus[del_target_main]["subs"]:
                    del_sub_name = st.selectbox("삭제 대상 소분류", menus[del_target_main]["subs"])
                    if st.form_submit_button("선택 삭제"):
                        menus[del_target_main]["subs"].remove(del_sub_name)
                        save_config(menus)
                        safe_rerun()

# 🟢 데이터 에디터 화면
else:
    st.header(f"📂 {selected_menu}")
    cat_type = menus[selected_menu]["type"]
    sub_tabs = menus[selected_menu]["subs"]
    
    df_current = st.session_state[f"df_{cat_type}"].copy()
    if not df_current.empty and "대분류" in df_current.columns:
        df_current['norm_main'] = df_current['대분류'].apply(normalize_str)
        filtered_main = df_current[df_current['norm_main'] == normalize_str(selected_menu)]
    else: filtered_main = pd.DataFrame()
    
    if not sub_tabs:
        st.info("설정 메뉴에서 하위 소분류를 구성해 주십시오.")
    else:
        tabs = st.tabs(sub_tabs)
        for i, tab in enumerate(tabs):
            with tab:
                current_sub = sub_tabs[i]
                expected_cols = get_expected_cols(selected_menu, current_sub, cat_type)
                display_cols = [c for c in expected_cols if c not in ["대분류", "소분류"]]
                
                if not filtered_main.empty and "소분류" in filtered_main.columns:
                    filtered_main_copy = filtered_main.copy()
                    filtered_main_copy['norm_sub'] = filtered_main_copy['소분류'].apply(normalize_str)
                    filtered_sub = filtered_main_copy[filtered_main_copy['norm_sub'] == normalize_str(current_sub)]
                else: filtered_sub = pd.DataFrame()
                
                for c in display_cols:
                    if c not in filtered_sub.columns: filtered_sub[c] = ""
                display_df = filtered_sub[display_cols]
                
                edited_df = st.data_editor(
                    display_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"editor_{selected_menu}_{current_sub}"
                )
                
                col_btn, _ = st.columns([2, 8])
                with col_btn:
                    if st.button(f"💾 데이터 영구 저장", key=f"save_{selected_menu}_{current_sub}"):
                        edited_df = edited_df.dropna(how="all")
                        edited_df["대분류"], edited_df["소분류"] = selected_menu, current_sub
                        
                        df_existing = load_data(cat_type)
                        if not df_existing.empty and "대분류" in df_existing.columns:
                            df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                                        (df_existing['소분류'].apply(normalize_str) == normalize_str(current_sub)))]
                        
                        df_final = pd.concat([df_existing, edited_df], ignore_index=True).fillna("")
                        save_data(df_final, cat_type)
                        st.success("데이터 동기화 완료!")
                        safe_rerun()
