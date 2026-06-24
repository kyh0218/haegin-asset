import streamlit as st
import pandas as pd
import io
import json
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Haegin Asset ERP", layout="wide", page_icon="🏢")

# ==============================================================================
# 🎨 UI/UX 커스텀 CSS (밝은 테마 + 하늘색 HAEGIN & 탭 강조)
# ==============================================================================
st.markdown("""
<style>
    /* 전체 배경: 깔끔한 연한 회색/흰색 톤 */
    .stApp { background-color: #F8FAFC; }
    
    /* 사이드바: 흰색 배경 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }
    
    /* 사이드바 라디오 버튼(대분류 탭) 디자인 */
    div[role="radiogroup"] > label {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        padding: 12px 20px !important;
        border-radius: 8px !important;
        margin-bottom: 8px !important;
        transition: all 0.2s ease;
    }
    div[role="radiogroup"] > label:hover {
        background-color: #F1F5F9 !important;
    }
    /* 선택된 대분류 탭 디자인 (하늘색 강조) */
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] {
        background-color: #00AEEF !important; /* 하늘색 */
        border-color: #00AEEF !important;
    }
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] * {
        color: #FFFFFF !important; /* 선택 시 글자는 흰색 */
        font-weight: bold !important;
    }
    /* 기본 라디오 동그라미 숨김 */
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    
    /* 메인 화면 여백 최소화 */
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    
    /* 일반 버튼 색상 (하늘색) */
    .stButton > button {
        background-color: #00AEEF !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
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
    "1. 해긴 비품 리스트": {"type": "비품", "subs": ["사무실&회의실", "휴게실 및 기타", "탕비실&카페테리아", "계절용품", "하이퍼라이즈 대여 비품"]},
    "2. PC 관리": {"type": "PC", "subs": ["전체 사용 PC 목록", "잔여재고", "모니터"]},
    "3. SW목록": {"type": "SW", "subs": ["백신", "Office", "Adobe", "3Ds Max", "VS 2022 pro", "Jetbrains&GitHub", "클로드", "업무용 AI 툴", "기타(구독형)", "기타(영구)", "윈도우", "한글&더존"]},
    "4. 보안모듈": {"type": "SW", "subs": ["보안모듈 통합"]},
    "5. 에셋&플러그인": {"type": "SW", "subs": ["에셋&플러그인 통합"]},
    "6. SW 구매내역": {"type": "SW", "subs": ["구매내역 통합"]}
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
    return COLS.get(dtype, COLS["비품"])

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
            if df.empty or "대분류" not in df.columns: return DEFAULT_CONFIG
            
            cfg = {}
            for _, row in df.iterrows():
                m = str(row.get("대분류", "")).strip()
                t = str(row.get("양식타입", "")).strip()
                s = str(row.get("소분류", "")).strip()
                
                if not m: continue
                if m not in cfg:
                    # 빈값이거나 에러가 나면 무조건 비품으로 초기화 (KeyError 원천 차단)
                    cfg[m] = {"type": t if t in ["비품", "SW", "PC"] else "비품", "subs": []}
                if s and s != "(소분류 없음)" and s not in cfg[m]["subs"]:
                    cfg[m]["subs"].append(s)
            
            # 하이퍼라이즈 탭 강제 유지
            if "1. 해긴 비품 리스트" in cfg and "하이퍼라이즈 대여 비품" not in cfg["1. 해긴 비품 리스트"]["subs"]:
                cfg["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
            
            return cfg
        except Exception as e:
            return DEFAULT_CONFIG
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

# --- 5. 사이드바 UI ---
# 로고 (하늘색 강조)
st.sidebar.markdown("""
<div style='text-align: center; margin-bottom: 20px;'>
    <h1 style='color: #00AEEF; margin: 0; font-size: 36px; font-weight: 900;'>HAEGIN</h1>
    <p style='color: #64748B; font-size: 14px; margin: 0; font-weight: 600;'>ASSET MANAGEMENT</p>
</div>
""", unsafe_allow_html=True)

nav_options = ["📊 통합 대시보드"]
menu_mapping = {}

# 실시간 데이터 건수 배지 계산
for k, v in menus.items():
    count = 0
    if v["type"] == "비품" and not df_eq.empty and "대분류" in df_eq.columns:
        count = len(df_eq[df_eq["대분류"] == k])
    elif v["type"] == "SW" and not df_sw.empty and "대분류" in df_sw.columns:
        count = len(df_sw[df_sw["대분류"] == k])
    elif v["type"] == "PC" and not df_pc.empty and "대분류" in df_pc.columns:
        count = len(df_pc[df_pc["대분류"] == k])
        
    label = f"📁 {k} [{count}]"
    nav_options.append(label)
    menu_mapping[label] = k

# 요청하신 수동입력/환경설정 탭 복구
nav_options.append("🛠️ 데이터 관리 (수동입력/삭제)")
nav_options.append("⚙️ 환경설정 (탭 관리)")

selected_label = st.sidebar.radio("Navigation", nav_options, label_visibility="collapsed")

st.sidebar.markdown("---")

# 엑셀 동기화 메뉴
if selected_label not in ["📊 통합 대시보드", "🛠️ 데이터 관리 (수동입력/삭제)", "⚙️ 환경설정 (탭 관리)"]:
    selected_menu = menu_mapping[selected_label]
    target_type = menus[selected_menu].get("type", "비품")
    sub_list = menus[selected_menu]["subs"] if menus[selected_menu]["subs"] else ["(소분류 없음)"]
    
    st.sidebar.markdown("<h4 style='color:#00AEEF;'>📁 데이터 일괄 동기화</h4>", unsafe_allow_html=True)
    target_sub = st.sidebar.selectbox("🎯 대상 탭 선택", sub_list)
    
    if st.sidebar.button("📝 빈 양식 엑셀 다운로드"):
        expected_cols = get_expected_cols(target_sub, target_type)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            pd.DataFrame(columns=[c for c in expected_cols if c not in ["대분류", "소분류"]]).to_excel(writer, index=False, sheet_name='입력양식')
        st.sidebar.download_button("📥 내 PC에 저장하기", data=buffer.getvalue(), file_name=f"{target_sub}_양식.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    uploaded_file = st.sidebar.file_uploader(f"🔄 [{target_sub}] 업로드", type=["xlsx", "csv"])
    if uploaded_file and st.sidebar.button("📥 구글 시트에 적용", use_container_width=True):
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
if selected_label == "📊 통합 대시보드":
    st.markdown("<h2 style='color:#333;'>📈 전사 자산/비품 통합 현황</h2>", unsafe_allow_html=True)
    
    eq_count = len(df_eq) if not df_eq.empty else 0
    pc_count = len(df_pc) if not df_pc.empty else 0
    sw_count = len(df_sw) if not df_sw.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📦 전체 하드웨어/비품", f"{int(eq_count + pc_count):,.0f} 개")
    c2.metric("💾 운용 소프트웨어", f"{sw_count:,.0f} 개")
    c3.metric("🏢 관리 탭 수", f"{len(menus)} 개")
    
    st.info("💡 왼쪽 메뉴에서 각 카테고리를 클릭하여 상세 리스트를 확인하고 표에서 직접 수정하세요.")

# 🟢 수동 데이터 관리 (추가 및 특정 탭 초기화) - 복구 완료
elif selected_label == "🛠️ 데이터 관리 (수동입력/삭제)":
    st.title("🛠️ 데이터 수동 등록 및 초기화")
    if not menus:
        st.warning("환경설정에서 대분류를 먼저 생성해주세요.")
    else:
        tab_manual, tab_clear = st.tabs(["➕ 건별 수동 등록", "🗑️ 특정 탭 데이터 비우기"])
        
        with tab_manual:
            target_main_manual = st.selectbox("등록할 대분류", list(menus.keys()))
            target_sub_manual = st.selectbox("등록할 소분류", menus[target_main_manual]["subs"] if menus[target_main_manual]["subs"] else ["(소분류 없음)"])
            dtype = menus[target_main_manual]["type"]
            expected_cols = get_expected_cols(target_sub_manual, dtype)
            
            with st.form("data_add_form", clear_on_submit=True):
                input_vals = {}
                form_cols = st.columns(3)
                for idx, col_name in enumerate(expected_cols[2:]):
                    col_ui = form_cols[idx % 3]
                    if col_name in ["개수", "취득가", "금액"]:
                        input_vals[col_name] = col_ui.number_input(col_name, value=0, step=1000)
                    else:
                        input_vals[col_name] = col_ui.text_input(col_name)
                if st.form_submit_button("➕ 1건 등록하기"):
                    new_row = {"대분류": target_main_manual, "소분류": target_sub_manual}
                    new_row.update(input_vals)
                    df_target = st.session_state[f"df_{dtype}"]
                    st.session_state[f"df_{dtype}"] = pd.concat([df_target, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(st.session_state[f"df_{dtype}"], dtype)
                    st.success("등록 완료!")
                    safe_rerun()
                    
        with tab_clear:
            st.warning("잘못 업로드된 특정 탭의 데이터를 통째로 지울 수 있습니다.")
            del_main = st.selectbox("지울 대분류 선택", list(menus.keys()), key="del_m")
            del_sub = st.selectbox("지울 소분류 선택", menus[del_main]["subs"] if menus[del_main]["subs"] else ["(소분류 없음)"], key="del_s")
            
            if st.button("🚨 해당 탭 데이터 전체 삭제", type="primary"):
                del_type = menus[del_main]["type"]
                df_existing = st.session_state[f"df_{del_type}"].copy()
                if not df_existing.empty and "대분류" in df_existing.columns:
                    df_existing = df_existing[
                        ~((df_existing['대분류'].apply(normalize_str) == normalize_str(del_main)) & 
                          (df_existing['소분류'].apply(normalize_str) == normalize_str(del_sub)))
                    ]
                    st.session_state[f"df_{del_type}"] = df_existing
                    save_data(df_existing, del_type)
                    st.success(f"[{del_sub}] 탭의 모든 데이터가 초기화되었습니다.")
                    safe_rerun()

# 🟢 환경설정 (탭 관리) - 복구 완료
elif selected_label == "⚙️ 환경설정 (탭 관리)":
    st.title("⚙️ 시스템 카테고리(탭) 관리")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ 대분류 추가")
        with st.form("add_main_form"):
            new_main_name = st.text_input("새 대분류 이름")
            new_main_type = st.selectbox("적용 양식", ["비품", "SW", "PC"])
            if st.form_submit_button("추가하기"):
                if new_main_name and new_main_name not in menus:
                    menus[new_main_name] = {"type": new_main_type, "subs": []}
                    save_config(menus)
                    safe_rerun()
                else: st.error("오류: 이름 중복 또는 공란")
        st.subheader("❌ 대분류 삭제")
        with st.form("del_main_form"):
            del_main_name = st.selectbox("삭제 대상", list(menus.keys()))
            if st.form_submit_button("선택 삭제") and del_main_name in menus:
                del menus[del_main_name]
                save_config(menus)
                safe_rerun()
    with c2:
        if menus:
            st.subheader("➕ 소분류(상단 탭) 추가")
            with st.form("add_sub_form"):
                target_main_conf = st.selectbox("상위 분류 선택", list(menus.keys()))
                new_sub_name = st.text_input("새 소분류 명칭")
                if st.form_submit_button("추가하기"):
                    if new_sub_name and new_sub_name not in menus[target_main_conf]["subs"]:
                        menus[target_main_conf]["subs"].append(new_sub_name)
                        save_config(menus)
                        safe_rerun()
            st.subheader("❌ 소분류(상단 탭) 삭제")
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
    cat_type = menus[selected_menu].get("type", "비품")
    sub_tabs = menus[selected_menu]["subs"]
    
    st.markdown(f"<h2 style='color:#333;'>📂 {selected_menu}</h2>", unsafe_allow_html=True)
    
    # 💡 [요청사항 완벽 반영] SW목록 전용 요약 대시보드
    if cat_type == "SW" and normalize_str(selected_menu) == normalize_str("3. SW목록"):
        st.markdown("### 💿 항목별 라이선스 현황 대시보드")
        sw_data = df_sw[df_sw["대분류"] == selected_menu] if not df_sw.empty and "대분류" in df_sw.columns else pd.DataFrame()
        
        if not sw_data.empty:
            summary_data = []
            for sub in sw_data["소분류"].unique():
                sub_df = sw_data[sw_data["소분류"] == sub]
                total_count = len(sub_df)
                
                # 사용자가 빈칸이 아닌 경우 '사용중'으로 카운트
                in_use_count = len(sub_df[sub_df["사용자"].astype(str).str.strip() != ""])
                
                # 사용기한이 기재된 데이터 중 가장 빨리 만료되는 날짜 찾기
                valid_dates = sub_df[sub_df["사용기한"].astype(str).str.strip() != ""]["사용기한"]
                nearest_expiry = valid_dates.min() if not valid_dates.empty else "-"
                
                summary_data.append({
                    "품목 (소분류)": sub,
                    "총 라이선스 개수": f"{total_count} EA",
                    "현재 사용중": f"{in_use_count} EA",
                    "가장 빠른 사용기한 (만료일)": nearest_expiry
                })
            
            # 현황판 표로 깔끔하게 노출
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        else:
            st.info("등록된 라이선스 내역이 없습니다.")
    
    st.markdown("---")
    
    # 하위 탭 및 에디터 렌더링
    df_master = df_eq if cat_type == "비품" else (df_sw if cat_type == "SW" else df_pc)
    
    if not sub_tabs:
        st.warning("상단 탭(소분류)이 없습니다. 환경설정에서 추가해주세요.")
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
