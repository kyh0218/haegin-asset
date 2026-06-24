import streamlit as st
import pandas as pd
import io
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Haegin Asset ERP", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }
    div[role="radiogroup"] > label {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 16px !important;
        border-radius: 6px !important;
        margin-bottom: 2px !important;
        transition: all 0.2s ease;
    }
    div[role="radiogroup"] > label:hover { background-color: #F1F5F9 !important; }
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] {
        background-color: #E0F2FE !important;
        border-left: 4px solid #00AEEF !important;
        border-radius: 0px 6px 6px 0px !important;
    }
    div[role="radiogroup"] > label[data-baseweb="radio"][aria-checked="true"] * {
        color: #0369A1 !important;
        font-weight: 800 !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p { font-size: 15px !important; }
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stButton > button {
        background-color: #00AEEF !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    HAS_CONN = True
except Exception as e:
    HAS_CONN = False
    st.error(f"구글 시트 연결 실패: {e}")

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

def load_data(dtype):
    if HAS_CONN:
        try:
            sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
            return conn.read(worksheet=sheet_name, ttl=30).fillna("")
        except: pass
    return pd.DataFrame(columns=COLS[dtype] if dtype != "비품" else COLS["비품"] + COLS["대여비품"])

def save_data(df, dtype):
    if HAS_CONN:
        sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
        conn.update(worksheet=sheet_name, data=df.fillna("").astype(str))
        st.cache_data.clear()
        st.cache_resource.clear()

def load_config():
    if HAS_CONN:
        try:
            df = conn.read(worksheet="menu_config", ttl=30).fillna("")
            if df.empty or "대분류" not in df.columns: return DEFAULT_CONFIG
            cfg = {}
            for _, row in df.iterrows():
                m = str(row.get("대분류", "")).strip()
                t = str(row.get("양식타입", "")).strip()
                s = str(row.get("소분류", "")).strip()
                if not m: continue
                if m not in cfg:
                    cfg[m] = {"type": t if t in ["비품", "SW", "PC"] else "비품", "subs": []}
                if s and s != "(소분류 없음)" and s not in cfg[m]["subs"]:
                    cfg[m]["subs"].append(s)
            if "1. 해긴 비품 리스트" in cfg and "하이퍼라이즈 대여 비품" not in cfg["1. 해긴 비품 리스트"]["subs"]:
                cfg["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
            return cfg
        except Exception:
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
        st.cache_resource.clear()

def render_equipment_dashboard(dash_df, current_sub):

    # ─── 하이퍼라이즈 대여 비품 전용 대시보드 ───
    if normalize_str(current_sub) == normalize_str("하이퍼라이즈 대여 비품"):
        st.markdown("<h4 style='color:#00AEEF; margin-top:10px;'>🏢 하이퍼라이즈 대여 비품 현황</h4>", unsafe_allow_html=True)

        if dash_df.empty:
            st.info("📭 아직 등록된 데이터가 없습니다. 아래 표에서 직접 입력하거나 엑셀을 업로드해 보세요.")
            st.markdown("---")
            return

        desk_col   = "책상 H-DE"
        chair_col  = "의자 H-HM"
        drawer_col = "서랍 H-DR"

        # 빈 값·nan만 제외하고 "번호없음" 포함 전체 카운트
        def count_items(series):
            return series.astype(str).str.strip().apply(
                lambda x: x != "" and x.lower() != "nan"
            ).sum()

        desk_total   = count_items(dash_df[desk_col])   if desk_col   in dash_df.columns else 0
        chair_total  = count_items(dash_df[chair_col])  if chair_col  in dash_df.columns else 0
        drawer_total = count_items(dash_df[drawer_col]) if drawer_col in dash_df.columns else 0
        total_rows   = len(dash_df)

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("📋 총 대여 세트 수", f"{total_rows:,} 세트")
        mc2.metric("🛋️ 책상 (H-DE)",   f"{int(desk_total):,} 개")
        mc3.metric("🪑 의자 (H-HM)",   f"{int(chair_total):,} 개")
        mc4.metric("🗄️ 서랍 (H-DR)",  f"{int(drawer_total):,} 개")

        st.markdown("<h4 style='color:#00AEEF; margin-top:20px;'>📋 대여 비품 상세 목록</h4>", unsafe_allow_html=True)
        display_cols = ["구분"] + [c for c in [desk_col, chair_col, drawer_col] if c in dash_df.columns]
        detail_df = dash_df[display_cols].copy().reset_index(drop=True)
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

        st.markdown("<hr style='margin: 20px 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)
        return

    # ─── 일반 비품 대시보드 ───
    if dash_df.empty:
        st.info("📭 아직 등록된 데이터가 없습니다. 아래 표에서 직접 입력하거나 엑셀을 업로드해 보세요.")
        st.markdown("---")
        return

    st.markdown("<h4 style='color:#00AEEF; margin-top:10px;'>📊 비품 현황 요약</h4>", unsafe_allow_html=True)

    total_kinds  = dash_df["품목"].nunique() if "품목" in dash_df.columns else 0
    total_count  = pd.to_numeric(dash_df.get("개수", pd.Series(dtype=float)), errors='coerce').fillna(0).sum()
    total_val    = (
        pd.to_numeric(dash_df.get("개수",   pd.Series(dtype=float)), errors='coerce').fillna(0) *
        pd.to_numeric(dash_df.get("취득가", pd.Series(dtype=float)), errors='coerce').fillna(0)
    ).sum() if "개수" in dash_df.columns and "취득가" in dash_df.columns else 0
    location_cnt = dash_df["위치"].nunique() if "위치" in dash_df.columns else 0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("품목 종류 수",  f"{int(total_kinds):,} 종")
    mc2.metric("총 수량",        f"{int(total_count):,} 개")
    mc3.metric("취득가 총액",    f"₩ {int(total_val):,.0f}")
    mc4.metric("관리 위치 수",   f"{location_cnt} 곳")

    st.markdown("<h4 style='color:#00AEEF; margin-top:20px;'>📋 품목별 상세 현황</h4>", unsafe_allow_html=True)

    if "품목" not in dash_df.columns or "개수" not in dash_df.columns:
        st.info("품목 또는 개수 컬럼이 없어 집계할 수 없습니다.")
        st.markdown("---")
        return

    dash_df = dash_df.copy()
    dash_df["개수_num"] = pd.to_numeric(dash_df["개수"], errors='coerce').fillna(0)
    item_summary = dash_df.groupby("품목", as_index=False).agg(총개수=("개수_num", "sum"))

    if "위치" in dash_df.columns:
        def loc_summary(grp):
            loc_grp = grp.groupby("위치")["개수_num"].sum().reset_index()
            loc_grp = loc_grp[loc_grp["위치"].astype(str).str.strip() != ""]
            if loc_grp.empty: return "-"
            return ", ".join(f"{r['위치']}({int(r['개수_num'])}개)" for _, r in loc_grp.iterrows())
        loc_map = dash_df.groupby("품목").apply(loc_summary).reset_index().rename(columns={0: "위치별 분포"})
        item_summary = item_summary.merge(loc_map, on="품목", how="left")

    if "최종확인 년도" in dash_df.columns:
        year_map = (
            dash_df[dash_df["최종확인 년도"].astype(str).str.strip() != ""]
            .groupby("품목")["최종확인 년도"].max().reset_index()
        )
        item_summary = item_summary.merge(year_map, on="품목", how="left")

    item_summary["총개수"] = item_summary["총개수"].astype(int)
    item_summary = (
        item_summary.rename(columns={"품목": "품목명", "총개수": "총 수량 (개)"})
                    .sort_values("총 수량 (개)", ascending=False)
                    .reset_index(drop=True)
    )
    st.dataframe(item_summary, use_container_width=True, hide_index=True)
    st.markdown("<hr style='margin: 20px 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)


# ─── 세션 초기화 ───
if HAS_CONN:
    menus = load_config()
    df_eq = load_data("비품")
    df_sw = load_data("SW")
    df_pc = load_data("PC")
else:
    st.stop()

# ─── 사이드바 ───
st.sidebar.markdown("""
<div style='text-align: center; margin-bottom: 20px;'>
    <h1 style='color: #00AEEF; margin: 0; font-size: 36px; font-weight: 900;'>HAEGIN</h1>
    <p style='color: #64748B; font-size: 14px; margin: 0; font-weight: 600;'>ASSET MANAGEMENT</p>
</div>
""", unsafe_allow_html=True)

nav_options  = ["📊 통합 대시보드"]
menu_mapping = {}

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

nav_options.append("🛠️ 데이터 관리 (수동입력/삭제)")
nav_options.append("⚙️ 환경설정 (탭 관리)")

selected_label = st.sidebar.radio("Navigation", nav_options, label_visibility="collapsed")
st.sidebar.markdown("---")

if selected_label not in ["📊 통합 대시보드", "🛠️ 데이터 관리 (수동입력/삭제)", "⚙️ 환경설정 (탭 관리)"]:
    selected_menu = menu_mapping[selected_label]
    target_type   = menus[selected_menu].get("type", "비품")
    sub_list      = menus[selected_menu]["subs"] if menus[selected_menu]["subs"] else ["(소분류 없음)"]

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
                df_existing = df_existing[
                    ~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) &
                      (df_existing['소분류'].apply(normalize_str) == normalize_str(target_sub)))
                ]
            df_final = pd.concat([df_existing, df_up], ignore_index=True).fillna("")
            save_data(df_final, target_type)
            st.cache_data.clear()
            st.cache_resource.clear()
            st.sidebar.success("✅ 동기화 완료! 최신 데이터를 불러옵니다.")
            safe_rerun()
        except Exception as e:
            st.sidebar.error(f"오류: {e}")

# ─── 메인 화면 ───

if selected_label == "📊 통합 대시보드":
    st.markdown("<h2 style='color:#333; margin-bottom: 30px;'>📈 전사 자산/비품 통합 현황</h2>", unsafe_allow_html=True)

    st.markdown("<h4 style='color:#00AEEF;'>💻 PC 자산 현황</h4>", unsafe_allow_html=True)
    pc_count = len(df_pc) if not df_pc.empty else 0
    pc_val   = pd.to_numeric(df_pc.get("금액", pd.Series()), errors='coerce').sum() if not df_pc.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("총 PC 관리 수량", f"{pc_count:,.0f} 대")
    c2.metric("PC 취득가 총액",  f"₩ {int(pc_val):,.0f}")
    if not df_pc.empty and "분류" in df_pc.columns:
        desktop_cnt = len(df_pc[df_pc["분류"].astype(str).str.contains("데스크탑", na=False)])
        laptop_cnt  = len(df_pc[df_pc["분류"].astype(str).str.contains("노트북|맥북|UMPC", na=False)])
        c3.metric("주요 기기 비율", f"데스크탑 {desktop_cnt}대 / 노트북 {laptop_cnt}대")
    else:
        c3.metric("주요 기기 비율", "데이터 없음")

    st.markdown("<hr style='margin: 30px 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)

    st.markdown("<h4 style='color:#00AEEF;'>📦 일반 비품 자산 현황</h4>", unsafe_allow_html=True)
    eq_count = pd.to_numeric(df_eq.get("개수", pd.Series()), errors='coerce').sum() if not df_eq.empty else 0
    eq_val   = (
        pd.to_numeric(df_eq["개수"],   errors='coerce').fillna(0) *
        pd.to_numeric(df_eq["취득가"], errors='coerce').fillna(0)
    ).sum() if not df_eq.empty and "개수" in df_eq.columns and "취득가" in df_eq.columns else 0
    c4, c5, c6 = st.columns(3)
    c4.metric("총 일반 비품 수량",    f"{int(eq_count):,.0f} 개")
    c5.metric("비품 취득가 총액",     f"₩ {int(eq_val):,.0f}")
    eq_tab_cnt = len(df_eq["소분류"].unique()) if not df_eq.empty and "소분류" in df_eq.columns else 0
    c6.metric("관리 중인 비품 탭 수", f"{eq_tab_cnt} 개")

    st.markdown("<hr style='margin: 30px 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)
    st.info("💡 왼쪽 탭을 클릭하여 상세 데이터를 조회하고 실시간으로 표를 수정해 보세요.")

elif selected_label == "🛠️ 데이터 관리 (수동입력/삭제)":
    st.title("🛠️ 데이터 수동 등록 및 초기화")
    if not menus:
        st.warning("환경설정에서 대분류를 먼저 생성해주세요.")
    else:
        tab_manual, tab_clear = st.tabs(["➕ 건별 수동 등록", "🗑️ 특정 탭 데이터 비우기"])
        with tab_manual:
            target_main_manual = st.selectbox("등록할 대분류", list(menus.keys()))
            target_sub_manual  = st.selectbox("등록할 소분류", menus[target_main_manual]["subs"] if menus[target_main_manual]["subs"] else ["(소분류 없음)"])
            dtype = menus[target_main_manual]["type"]
            expected_cols = get_expected_cols(target_sub_manual, dtype)
            with st.form("data_add_form", clear_on_submit=True):
                input_vals = {}
                form_cols  = st.columns(3)
                for idx, col_name in enumerate(expected_cols[2:]):
                    col_ui = form_cols[idx % 3]
                    if col_name in ["개수", "취득가", "금액"]:
                        input_vals[col_name] = col_ui.number_input(col_name, value=0, step=1000)
                    else:
                        input_vals[col_name] = col_ui.text_input(col_name)
                if st.form_submit_button("➕ 1건 등록하기"):
                    new_row = {"대분류": target_main_manual, "소분류": target_sub_manual}
                    new_row.update(input_vals)
                    df_target = load_data(dtype)
                    save_data(pd.concat([df_target, pd.DataFrame([new_row])], ignore_index=True), dtype)
                    st.success("등록 완료!")
                    safe_rerun()
        with tab_clear:
            st.warning("잘못 업로드된 특정 탭의 데이터를 통째로 지울 수 있습니다.")
            del_main = st.selectbox("지울 대분류 선택", list(menus.keys()), key="del_m")
            del_sub  = st.selectbox("지울 소분류 선택", menus[del_main]["subs"] if menus[del_main]["subs"] else ["(소분류 없음)"], key="del_s")
            if st.button("🚨 해당 탭 데이터 전체 삭제", type="primary"):
                del_type    = menus[del_main]["type"]
                df_existing = load_data(del_type)
                if not df_existing.empty and "대분류" in df_existing.columns:
                    df_existing = df_existing[
                        ~((df_existing['대분류'].apply(normalize_str) == normalize_str(del_main)) &
                          (df_existing['소분류'].apply(normalize_str) == normalize_str(del_sub)))
                    ]
                    save_data(df_existing, del_type)
                    st.success(f"[{del_sub}] 탭의 모든 데이터가 초기화되었습니다.")
                    safe_rerun()

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
                new_sub_name     = st.text_input("새 소분류 명칭")
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

# ─── 개별 탭 조회 및 에디터 ───
else:
    selected_menu = menu_mapping[selected_label]
    cat_type      = menus[selected_menu].get("type", "비품")
    sub_tabs      = menus[selected_menu]["subs"]

    st.markdown(f"<h2 style='color:#333;'>📂 {selected_menu}</h2>", unsafe_allow_html=True)

    if cat_type == "SW" and normalize_str(selected_menu) == normalize_str("3. SW목록"):
        st.markdown("<h4 style='color:#00AEEF; margin-top: 10px;'>💿 라이선스 요약 대시보드</h4>", unsafe_allow_html=True)
        sw_data = df_sw[df_sw["대분류"].apply(normalize_str) == normalize_str(selected_menu)] if not df_sw.empty and "대분류" in df_sw.columns else pd.DataFrame()
        if not sw_data.empty and "사용자" in sw_data.columns:
            total_sw = len(sw_data)
            used_sw  = len(sw_data[sw_data["사용자"].astype(str).str.strip() != ""])
            avail_sw = total_sw - used_sw
            c1, c2, c3 = st.columns(3)
            c1.metric("총 발급 라이선스",  f"{total_sw} EA")
            c2.metric("할당 완료 (사용중)", f"{used_sw} EA")
            c3.metric("잔여 (미사용)",      f"{avail_sw} EA")
            st.markdown("<br>", unsafe_allow_html=True)
        if not sw_data.empty and "소분류" in sw_data.columns:
            summary_data = []
            for sub in sw_data["소분류"].unique():
                if not sub: continue
                sub_df       = sw_data[sw_data["소분류"] == sub]
                total_count  = len(sub_df)
                in_use_count = len(sub_df[sub_df["사용자"].astype(str).str.strip() != ""]) if "사용자" in sub_df.columns else 0
                if "사용기한" in sub_df.columns:
                    valid_dates    = sub_df[sub_df["사용기한"].astype(str).str.strip() != ""]["사용기한"]
                    nearest_expiry = valid_dates.min() if not valid_dates.empty else "-"
                else:
                    nearest_expiry = "-"
                summary_data.append({
                    "품목 (소분류)": sub,
                    "총 라이선스 개수": f"{total_count} EA",
                    "현재 사용중": f"{in_use_count} EA",
                    "가장 빠른 만료일": nearest_expiry
                })
            if summary_data:
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
            else:
                st.info("표시할 라이선스 내역이 없습니다.")
        else:
            st.info("등록된 소프트웨어 데이터가 없습니다.")
        st.markdown("<hr style='margin: 30px 0; border-color: #E2E8F0;'>", unsafe_allow_html=True)
    else:
        st.markdown("---")

    df_master = df_eq if cat_type == "비품" else (df_sw if cat_type == "SW" else df_pc)

    if not sub_tabs:
        st.warning("상단 탭(소분류)이 없습니다. 환경설정에서 추가해주세요.")
    else:
        tabs = st.tabs(sub_tabs)
        for i, current_sub in enumerate(sub_tabs):
            with tabs[i]:

                # 비품 타입 → 대시보드 렌더링
                if cat_type == "비품":
                    if not df_master.empty and "대분류" in df_master.columns and "소분류" in df_master.columns:
                        dash_df = df_master[
                            (df_master["대분류"].apply(normalize_str) == normalize_str(selected_menu)) &
                            (df_master["소분류"].apply(normalize_str) == normalize_str(current_sub))
                        ].copy()
                    else:
                        dash_df = pd.DataFrame()
                    render_equipment_dashboard(dash_df, current_sub)

                # 기존 에디터
                st.caption("✨ 아래 표를 더블 클릭하여 내용을 즉시 수정하거나, 맨 아래 빈 칸을 눌러 행을 추가하세요.")
                expected_cols = get_expected_cols(current_sub, cat_type)
                display_cols  = [c for c in expected_cols if c not in ["대분류", "소분류"]]

                if not df_master.empty and "대분류" in df_master.columns and "소분류" in df_master.columns:
                    f_df = df_master[
                        (df_master["대분류"].apply(normalize_str) == normalize_str(selected_menu)) &
                        (df_master["소분류"].apply(normalize_str) == normalize_str(current_sub))
                    ]
                else:
                    f_df = pd.DataFrame()

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
                        df_existing = df_existing[
                            ~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) &
                              (df_existing['소분류'].apply(normalize_str) == normalize_str(current_sub)))
                        ]
                    df_final = pd.concat([df_existing, edited_df], ignore_index=True).fillna("")
                    save_data(df_final, cat_type)
                    st.success("구글 클라우드 DB에 완벽히 저장되었습니다!")
                    safe_rerun()
