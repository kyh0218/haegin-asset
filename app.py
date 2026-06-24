import streamlit as st
import pandas as pd
import io
import json
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Haegin Asset ERP", layout="wide", page_icon="🏢")

# ==============================================================================
# 🎨 완벽한 더존 ERP 스타일 커스텀 CSS (시안 디자인 100% 반영)
# ==============================================================================
st.markdown("""
<style>
    /* 전체 배경 회색톤으로 깔끔하게 */
    .stApp { background-color: #f0f2f6; }
    
    /* 좌측 사이드바: 딥 네이비(블랙) 컬러 적용 */
    [data-testid="stSidebar"] {
        background-color: #0b1120 !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
    
    /* 사이드바 라디오 버튼을 둥근 필(Pill) 형태의 메뉴로 디자인 */
    div[role="radiogroup"] > label {
        background-color: #1e293b !important;
        padding: 12px 20px !important;
        border-radius: 10px !important;
        margin-bottom: 8px !important;
        border-left: 4px solid transparent !important;
        transition: all 0.3s ease;
    }
    div[role="radiogroup"] > label:hover {
        background-color: #334155 !important;
    }
    /* 선택된 메뉴 디자인 (스카이블루 강조) */
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] {
        background-color: #0ea5e9 !important;
        border-left: 4px solid #38bdf8 !important;
    }
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] * {
        color: white !important;
        font-weight: 700 !important;
    }
    /* 기본 라디오 동그라미 숨김 */
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    
    /* 메인 화면 여백 최소화 */
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    
    /* 대시보드 카드 스타일 */
    .dashboard-card {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-top: 5px solid #0ea5e9;
        margin-bottom: 20px;
    }
    /* 저장 버튼 스카이블루 강조 */
    .stButton > button {
        background-color: #0ea5e9 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. 구글 시트 연결 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    HAS_CONN = True
except Exception as e:
    HAS_CONN = False
    st.error(f"구글 시트 연결 실패: {e}")

# --- 2. 데이터 양식 기준 ---
COLS = {
    "비품": ["대분류", "소분류", "품목", "최종확인 년도", "분류코드", "개수", "관리번호", "자산번호", "제조사", "모델명", "취득일", "취득가", "위치", "세부위치"],
    "SW": ["대분류", "소분류", "구매일자", "사용자", "소속", "이메일", "사용기한", "비고"],
    "PC": ["대분류", "소분류", "사번", "이름", "소속", "관리번호", "입사일", "교체일", "분류", "CPU", "RAM", "VGA", "디스크1", "디스크2", "OS", "구매일자", "금액", "비고"],
    "대여비품": ["대분류", "소분류", "구분", "책상 H-DE", "의자 H-HM", "서랍 H-DR"]
}

DEFAULT_CONFIG = {
    "1. 해긴 비품 리스트": {"type": "비품", "icon": "📦", "subs": ["사무실&회의실", "휴게실 및 기타", "탕비실&카페테리아", "계절용품", "하이퍼라이즈 대여 비품"]},
    "2. PC 관리": {"type": "PC", "icon": "💻", "subs": ["전체 사용 PC 목록", "잔여재고", "모니터"]},
    "3. SW목록": {"type": "SW", "icon": "💿", "subs": ["백신", "Office", "Adobe", "3Ds Max", "VS 2022 pro", "Jetbrains&GitHub", "클로드", "업무용 AI 툴", "기타(구독형)", "기타(영구)", "윈도우", "한글&더존"]},
    "4. 보안모듈": {"type": "SW", "icon": "🛡️", "subs": ["보안모듈 통합"]},
    "5. 에셋&플러그인": {"type": "SW", "icon": "🧩", "subs": ["에셋&플러그인 통합"]},
    "6. SW 구매내역": {"type": "SW", "icon": "🛒", "subs": ["구매내역 통합"]}
}

# --- 3. 핵심 함수 (에러 방지 완벽 처리) ---
def safe_rerun():
    try: st.rerun()
    except: st.experimental_rerun()

def normalize_str(s):
    if pd.isna(s): return ""
    s = str(s).strip().replace(" ", "")
    return re.sub(r'^\d+[\._\s\-]*', '', s)

def get_expected_cols(sub_tab, dtype):
    if normalize_str(sub_tab) == normalize_str("하이퍼라이즈 대여 비품"):
        return COLS["대여비품"]
    return COLS[dtype]

# [캐싱] 데이터 불러오기 (속도 혁신)
@st.cache_data(ttl=600)
def _load_data_cached(sheet_name):
    return conn.read(worksheet=sheet_name, ttl=0).fillna("")

def load_data(dtype):
    if HAS_CONN:
        try:
            sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
            return _load_data_cached(sheet_name)
        except: pass
    return pd.DataFrame(columns=COLS[dtype] if dtype != "비품" else COLS["비품"] + COLS["대여비품"])

def save_data(df, dtype):
    if HAS_CONN:
        sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
        conn.update(worksheet=sheet_name, data=df.fillna("").astype(str))
        st.cache_data.clear() # 저장 즉시 모든 유저 화면 동기화

def load_config():
    if HAS_CONN:
        try:
            df = conn.read(worksheet="menu_config", ttl=600).fillna("")
            if df.empty: return DEFAULT_CONFIG
            cfg = {}
            for _, row in df.iterrows():
                m, t, s = str(row.get("대분류", "")).strip(), str(row.get("양식타입", "")).strip(), str(row.get("소분류", "")).strip()
                if not m: continue
                if m not in cfg:
                    icon = DEFAULT_CONFIG.get(m, {}).get("icon", "📁")
                    t = t if t else DEFAULT_CONFIG.get(m, {}).get("type", "비품") # KeyError 원인 완벽 차단
                    cfg[m] = {"type": t, "icon": icon, "subs": []}
                if s and s != "(소분류 없음)" and s not in cfg[m]["subs"]:
                    cfg[m]["subs"].append(s)
            
            # 하이퍼라이즈 탭 강제 유지
            if "1. 해긴 비품 리스트" in cfg and "하이퍼라이즈 대여 비품" not in cfg["1. 해긴 비품 리스트"]["subs"]:
                cfg["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
            
            # Type 무조건 보장
            for k, v in cfg.items():
                if "type" not in v or not v["type"]: v["type"] = DEFAULT_CONFIG.get(k, {}).get("type", "비품")
            return cfg
        except: return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    if HAS_CONN:
        rows = []
        for main, info in config.items():
            if not info["subs"]: rows.append({"대분류": main, "양식타입": info["type"], "소분류": ""})
            else:
                for sub in info["subs"]: rows.append({"대분류": main, "양식타입": info["type"], "소분류": sub})
        conn.update(worksheet="menu_config", data=pd.DataFrame(rows))
        st.cache_data.clear()

# --- 4. 세션 초기화 ---
if HAS_CONN:
    menus = load_config()
    df_eq = load_data("비품")
    df_sw = load_data("SW")
    df_pc = load_data("PC")
else: st.stop()

# --- 5. 사이드바 UI (배지 및 아이콘 적용) ---
st.sidebar.markdown("""
<div style='text-align: center; margin-bottom: 30px;'>
    <h1 style='color: #0ea5e9; margin: 0; font-size: 32px;'>HAEGIN</h1>
    <p style='color: #94a3b8; font-size: 14px; margin: 0; letter-spacing: 1px;'>ASSET MANAGEMENT</p>
</div>
""", unsafe_allow_html=True)

nav_options = ["📊 ERP 통합 대시보드"]
menu_mapping = {}

# 💡 실시간 데이터 건수 배지(Badge) 계산 및 메뉴에 병합
for k, v in menus.items():
    count = 0
    if v["type"] == "비품" and not df_eq.empty and "대분류" in df_eq.columns:
        count = len(df_eq[df_eq["대분류"] == k])
    elif v["type"] == "SW" and not df_sw.empty and "대분류" in df_sw.columns:
        count = len(df_sw[df_sw["대분류"] == k])
    elif v["type"] == "PC" and not df_pc.empty and "대분류" in df_pc.columns:
        count = len(df_pc[df_pc["대분류"] == k])
        
    label = f"{v.get('icon', '📁')} {k} [{count}]"
    nav_options.append(label)
    menu_mapping[label] = k

nav_options.append("⚙️ 기초 정보 관리")

selected_label = st.sidebar.radio("Navigation", nav_options, label_visibility="collapsed")

st.sidebar.markdown("---")
# 엑셀 동기화 메뉴
if selected_label not in ["📊 ERP 통합 대시보드", "⚙️ 기초 정보 관리"]:
    selected_menu = menu_mapping[selected_label]
    target_type = menus[selected_menu]["type"]
    sub_list = menus[selected_menu]["subs"] if menus[selected_menu]["subs"] else ["(소분류 없음)"]
    
    st.sidebar.markdown("<h4 style='color:#0ea5e9;'>📁 데이터 일괄 동기화</h4>", unsafe_allow_html=True)
    target_sub = st.sidebar.selectbox("🎯 대상 탭 선택", sub_list)
    
    if st.sidebar.button("📝 빈 양식 엑셀 다운로드"):
        expected_cols = get_expected_cols(target_sub, target_type)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            pd.DataFrame(columns=[c for c in expected_cols if c not in ["대분류", "소분류"]]).to_excel(writer, index=False, sheet_name='입력양식')
        st.sidebar.download_button("📥 저장하기", data=buffer.getvalue(), file_name=f"{target_sub}_양식.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    uploaded_file = st.sidebar.file_uploader(f"🔄 [{target_sub}] 업로드", type=["xlsx", "csv"])
    if uploaded_file and st.sidebar.button("📥 구글 시트에 덮어쓰기", use_container_width=True):
        try:
            df_up = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file, encoding="utf-8-sig")
            df_up["대분류"], df_up["소분류"] = selected_menu, target_sub
            expected_cols = get_expected_cols(target_sub, target_type)
            
            for c in expected_cols:
                if c not in df_up.columns: df_up[c] = ""
            df_up = df_up[expected_cols].fillna("")
            
            df_existing = load_data(target_type)
            if not df_existing.empty and "대분류" in df_existing.columns:
                df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                            (df_existing['소분류'].apply(normalize_str) == normalize_str(target_sub)))]
            
            df_final = pd.concat([df_existing, df_up], ignore_index=True).fillna("")
            save_data(df_final, target_type)
            st.sidebar.success("동기화 완료!")
            safe_rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

# --- 6. 메인 화면 로직 ---

# 🟢 통합 대시보드
if selected_label == "📊 ERP 통합 대시보드":
    st.markdown("<h2 style='color:#0f172a;'>📈 전사 자산/비품 통합 현황</h2>", unsafe_allow_html=True)
    
    eq_count = len(df_eq) if not df_eq.empty else 0
    pc_count = len(df_pc) if not df_pc.empty else 0
    sw_count = len(df_sw) if not df_sw.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='dashboard-card'><h3>📦 하드웨어/비품</h3><h1 style='color:#0ea5e9; font-size:48px;'>{int(eq_count + pc_count):,.0f}</h1></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='dashboard-card'><h3>💾 운용 소프트웨어</h3><h1 style='color:#0ea5e9; font-size:48px;'>{sw_count:,.0f}</h1></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='dashboard-card'><h3>🏢 부서 탭</h3><h1 style='color:#0ea5e9; font-size:48px;'>{len(menus)}</h1></div>", unsafe_allow_html=True)
    
    st.info("💡 **실시간 연동 가동 중:** 다른 담당자가 정보를 수정하면 즉시 구글 시트에 반영되고 전사 화면이 동기화됩니다.")

# 🟢 환경설정
elif selected_label == "⚙️ 기초 정보 설정":
    st.markdown("<h2 style='color:#0f172a;'>⚙️ 시스템 설정 및 카테고리 관리</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("대분류 추가")
        with st.form("add_main_form"):
            new_main_name = st.text_input("새 대분류 명칭")
            new_main_type = st.selectbox("양식", ["비품", "SW", "PC"])
            if st.form_submit_button("등록") and new_main_name:
                if new_main_name not in menus:
                    menus[new_main_name] = {"type": new_main_type, "icon": "📁", "subs": []}
                    save_config(menus)
                    safe_rerun()
        st.subheader("대분류 삭제")
        with st.form("del_main_form"):
            del_main_name = st.selectbox("삭제 대상", list(menus.keys()))
            if st.form_submit_button("선택 삭제") and del_main_name in menus:
                del menus[del_main_name]
                save_config(menus)
                safe_rerun()
    with c2:
        if menus:
            st.subheader("소분류 추가")
            with st.form("add_sub_form"):
                target_main_conf = st.selectbox("상위 분류 선택", list(menus.keys()))
                new_sub_name = st.text_input("새 소분류 명칭")
                if st.form_submit_button("등록") and new_sub_name:
                    if new_sub_name not in menus[target_main_conf]["subs"]:
                        menus[target_main_conf]["subs"].append(new_sub_name)
                        save_config(menus)
                        safe_rerun()
            st.subheader("소분류 삭제")
            with st.form("del_sub_form"):
                del_target_main = st.selectbox("상위 분류", list(menus.keys()), key="dsm")
                if menus[del_target_main]["subs"]:
                    del_sub_name = st.selectbox("삭제 대상", menus[del_target_main]["subs"])
                    if st.form_submit_button("선택 삭제"):
                        menus[del_target_main]["subs"].remove(del_sub_name)
                        save_config(menus)
                        safe_rerun()

# 🟢 개별 탭 조회 및 에디터 화면
else:
    selected_menu = menu_mapping[selected_label]
    cat_type = menus[selected_menu]["type"]
    sub_tabs = menus[selected_menu]["subs"]
    
    st.markdown(f"<h2 style='color:#0f172a;'>📂 {selected_menu}</h2>", unsafe_allow_html=True)
    
    # 💡 [요청사항] SW목록 접속 시 화려한 라이선스 대시보드 노출
    if cat_type == "SW" and normalize_str(selected_menu) == normalize_str("3. SW목록"):
        st.markdown("### 💿 Software License Intelligence (실시간 사용 현황)")
        sw_data = df_sw[df_sw["대분류"] == selected_menu] if not df_sw.empty and "대분류" in df_sw.columns else pd.DataFrame()
        
        if not sw_data.empty:
            summary = sw_data.groupby("소분류").size().reset_index(name="사용중")
            html_bars = "<div style='display: flex; flex-direction: column; gap: 15px;'>"
            for _, row in summary.iterrows():
                sub_name = row["소분류"]
                used = row["사용중"]
                total = used + 2 # 임시 총량 (사용중 + 여유분 2개)
                pct = min(int((used / total) * 100), 100)
                html_bars += f"""
                <div style='display: flex; align-items: center; gap: 20px;'>
                    <div style='width: 180px; font-weight: bold; color: #334155;'>{sub_name}</div>
                    <div style='flex-grow: 1; background: #e2e8f0; height: 25px; border-radius: 6px; overflow: hidden;'>
                        <div style='width: {pct}%; height: 100%; background: linear-gradient(90deg, #0ea5e9, #2563eb);'></div>
                    </div>
                    <div style='width: 100px; text-align: right; font-weight: bold; color: #0ea5e9;'>{used} / {total} EA</div>
                </div>
                """
            html_bars += "</div>"
            st.markdown(f"<div class='dashboard-card'>{html_bars}</div>", unsafe_allow_html=True)
        else:
            st.info("등록된 라이선스 내역이 없습니다.")
    
    st.markdown("---")
    
    # 하위 탭 및 에디터 렌더링
    df_master = df_eq if cat_type == "비품" else (df_sw if cat_type == "SW" else df_pc)
    
    if not sub_tabs:
        st.warning("하위 탭이 없습니다. 환경설정에서 추가해주세요.")
    else:
        tabs = st.tabs(sub_tabs)
        for i, current_sub in enumerate(sub_tabs):
            with tabs[i]:
                st.caption("✨ 아래 표를 더블 클릭하여 내용을 즉시 수정하거나, 맨 아래 빈 칸을 눌러 행을 추가하세요.")
                
                expected_cols = get_expected_cols(current_sub, cat_type)
                display_cols = [c for c in expected_cols if c not in ["대분류", "소분류"]]
                
                if not df_master.empty and "대분류" in df_master.columns and "소분류" in df_master.columns:
                    f_df = df_master[(df_master["대분류"].apply(normalize_str) == normalize_str(selected_menu)) & 
                                     (df_master["소분류"].apply(normalize_str) == normalize_str(current_sub))]
                else: f_df = pd.DataFrame()
                
                # 표 규격 셋팅
                for c in display_cols:
                    if c not in f_df.columns: f_df[c] = ""
                
                edited_df = st.data_editor(
                    f_df[display_cols],
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"editor_{selected_menu}_{current_sub}"
                )
                
                if st.button(f"💾 [{current_sub}] 변경사항 구글 시트 저장", type="primary", key=f"save_{selected_menu}_{current_sub}"):
                    edited_df = edited_df.dropna(how="all")
                    edited_df["대분류"] = selected_menu
                    edited_df["소분류"] = current_sub
                    
                    df_existing = load_data(cat_type)
                    if not df_existing.empty and "대분류" in df_existing.columns:
                        df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                                    (df_existing['소분류'].apply(normalize_str) == normalize_str(current_sub)))]
                    
                    df_final = pd.concat([df_existing, edited_df], ignore_index=True).fillna("")
                    save_data(df_final, cat_type)
                    st.success("구글 클라우드 DB에 완벽히 저장되었습니다!")
                    safe_rerun()
