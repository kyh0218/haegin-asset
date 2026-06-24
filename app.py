import streamlit as st
import pandas as pd
import io
import json
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="해긴 자산/비품 통합 관리", layout="wide")

# --- 1. 구글 스프레드시트 커넥션 연결 ---
# Streamlit Secrets에 저장된 자격증명을 기반으로 구글 시트와 통신합니다.
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    HAS_CONN = True
except Exception as e:
    HAS_CONN = False
    st.error(f"구글 시트 연결 실패. Secrets 설정을 확인하세요. 에러: {e}")

# --- 2. 엑셀 양식 기준 (특수 탭 분리 적용) ---
COLS = {
    "비품": ["대분류", "소분류", "품목", "최종확인 년도", "분류코드", "개수", "관리번호", "자산번호", "제조사", "모델명", "취득일", "취득가", "위치", "세부위치"],
    "SW": ["대분류", "소분류", "구매일자", "사용자", "소속", "이메일", "사용기한", "비고"],
    "PC": ["대분류", "소분류", "사번", "이름", "소속", "관리번호", "입사일", "교체일", "분류", "CPU", "RAM", "VGA", "디스크1", "디스크2", "OS", "구매일자", "금액", "비고"],
    "대여비품": ["대분류", "소분류", "구분", "책상 H-DE", "의자 H-HM", "서랍 H-DR"] # 하이퍼라이즈 전용
}

# --- 3. 유틸리티 및 데이터 입출력 함수 (구글 시트 최적화) ---
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
            # menu_config 탭에서 구조화된 테이블을 읽어 딕셔너리로 복원
            df_conf = conn.read(worksheet="menu_config", ttl=0).fillna("")
            if df_conf.empty: return default_config
            
            config = {}
            for _, row in df_conf.iterrows():
                main = str(row["대분류"]).strip()
                dtype = str(row["양식타입"]).strip()
                sub = str(row["소분류"]).strip()
                if not main: continue
                if main not in config:
                    config[main] = {"type": dtype, "subs": []}
                if sub and sub != "(소분류 없음)" and sub not in config[main]["subs"]:
                    config[main]["subs"].append(sub)
            
            # 하이퍼라이즈 대여 비품 누락 방지 안전 장치
            if "1. 해긴 비품 리스트" in config and "하이퍼라이즈 대여 비품" not in config["1. 해긴 비품 리스트"]["subs"]:
                config["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
            return config
        except:
            return default_config
    return default_config

# [구글 시트 연동] 메뉴 설정 저장하기
def save_config(config):
    if HAS_CONN:
        rows = []
        for main, info in config.items():
            if not info["subs"]:
                rows.append({"대분류": main, "양식타입": info["type"], "소분류": ""})
            else:
                for sub in info["subs"]:
                    rows.append({"대분류": main, "양식타입": info["type"], "소분류": sub})
        df_conf = pd.DataFrame(rows)
        conn.update(worksheet="menu_config", data=df_conf)

# [구글 시트 연동] 메인 자산 데이터 불러오기
def load_data(dtype):
    if HAS_CONN:
        try:
            sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
            df = conn.read(worksheet=sheet_name, ttl=0).fillna("")
            # 하이퍼라이즈 탭이나 동적 열 확장을 위해 들어오는 대로 열 구조 유지
            return df
        except:
            pass
    # 첫 개설 시 빈 틀 제공
    return pd.DataFrame(columns=COLS[dtype] if dtype != "비품" else COLS["비품"] + COLS["대여비품"])

# [구글 시트 연동] 메인 자산 데이터 저장하기
def save_data(df, dtype):
    if HAS_CONN:
        sheet_name = f"data_{'equipment' if dtype=='비품' else ('software' if dtype=='SW' else 'pc')}"
        df_to_save = df.fillna("").astype(str)
        conn.update(worksheet=sheet_name, data=df_to_save)

# --- 4. 데이터 실시간 동기화 및 세션 바인딩 ---
if HAS_CONN:
    st.session_state.menu_config = load_config()
    st.session_state.df_비품 = load_data("비품")
    st.session_state.df_SW = load_data("SW")
    st.session_state.df_PC = load_data("PC")
else:
    st.stop() # 연결이 유효하지 않으면 프로세스 일시중단

menus = st.session_state.menu_config
eq_df = st.session_state.df_비품
sw_df = st.session_state.df_SW
pc_df = st.session_state.df_PC

# --- 5. 사이드바 네비게이션 ---
st.sidebar.title("🏢 해긴 자산 관리")
nav_list = ["📊 통합 대시보드"] + list(menus.keys()) + ["⚙️ 환경설정 (탭 관리)"]
selected_menu = st.sidebar.radio("이동할 화면 선택:", nav_list)

st.sidebar.markdown("---")

# --- 6. 엑셀 다운로드 및 스마트 업로드 로직 ---
st.sidebar.header("📁 데이터 동기화")
if selected_menu not in ["📊 통합 대시보드", "⚙️ 환경설정 (탭 관리)"]:
    sub_list = menus[selected_menu]["subs"] if menus[selected_menu]["subs"] else ["(소분류 없음)"]
    target_sub = st.sidebar.selectbox("🎯 대상 탭을 고르세요", sub_list)
    target_type = menus[selected_menu]["type"]
    expected_cols = get_expected_cols(selected_menu, target_sub, target_type)
    
    if st.sidebar.button("📝 이 탭에 맞는 빈 양식 다운로드"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            clean_cols = [c for c in expected_cols if c not in ["대분류", "소분류"]]
            pd.DataFrame(columns=clean_cols).to_excel(writer, index=False, sheet_name='입력양식')
        st.sidebar.download_button("📥 내 PC에 저장하기", data=buffer.getvalue(), file_name=f"{target_sub}_양식.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    st.sidebar.markdown("---")
    upload_mode = st.sidebar.radio("업로드 방식:", ["현재 탭 데이터 교체 (안전함)", "현재 탭 아래에 이어붙이기"])
    uploaded_file = st.sidebar.file_uploader(f"🔄 [{target_sub}] 엑셀 업로드", type=["xlsx", "csv"])

    if uploaded_file:
        st.sidebar.error("⚠️ 아래 [적용하기] 버튼을 꼭 누르세요!")
        if st.sidebar.button("📥 시스템에 최종 적용하기", type="primary", use_container_width=True):
            try:
                if uploaded_file.name.endswith(".xlsx"): df_up = pd.read_excel(uploaded_file)
                else: df_up = pd.read_csv(uploaded_file, encoding="utf-8-sig")
                
                df_up["대분류"] = selected_menu
                df_up["소분류"] = target_sub
                
                for c in expected_cols:
                    if c not in df_up.columns: df_up[c] = ""
                df_up = df_up[expected_cols].fillna("")
                
                df_existing = load_data(target_type)
                if upload_mode == "현재 탭 데이터 교체 (안전함)":
                    if not df_existing.empty and "대분류" in df_existing.columns:
                        df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                                    (df_existing['소분류'].apply(normalize_str) == normalize_str(target_sub)))]
                
                df_final = pd.concat([df_existing, df_up], ignore_index=True).fillna("")
                save_data(df_final, target_type)
                st.sidebar.success(f"성공! 구글 시트와 실시간 연동 완료.")
                safe_rerun()
            except Exception as e:
                st.sidebar.error(f"오류: {e}")

# --- 7. 메인 화면 로직 ---

# 🟢 1) 통합 대시보드
if selected_menu == "📊 통합 대시보드":
    st.title("📦 해긴 자산 통합 대시보드")
    
    eq_count = pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').sum() if not eq_df.empty else 0
    eq_val = (pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').fillna(0) * pd.to_numeric(eq_df.get("취득가", pd.Series()), errors='coerce').fillna(0)).sum() if not eq_df.empty else 0
    pc_count = len(pc_df)
    pc_val = pd.to_numeric(pc_df.get("금액", pd.Series()), errors='coerce').sum() if not pc_df.empty else 0
    sw_count = len(sw_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 전체 비품/기기 수량", f"{int(eq_count + pc_count):,.0f} 개")
    col2.metric("💾 관리 중인 SW 라이선스", f"{sw_count:,.0f} 개")
    col3.metric("💰 총 자산 가치 합산", f"₩ {int(eq_val + pc_val):,.0f}")
    st.markdown("---")
    st.success("🌐 **구글 스프레드시트 클라우드 데이터베이스 연동 활성화 완료**")
    st.info("5명의 팀원이 어디서나 접속하여 데이터를 수정하면 구글 시트에 실시간 공유 저장됩니다.")

# 🟢 2) 탭 관리 (환경설정)
elif selected_menu == "⚙️ 환경설정 (탭 관리)":
    st.title("⚙️ 시스템 카테고리(탭) 관리")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ 대분류 추가")
        with st.form("add_main_form"):
            new_main_name = st.text_input("새 대분류 이름 (예: 7. 차량 관리)")
            new_main_type = st.selectbox("적용 양식", ["비품", "SW", "PC"])
            if st.form_submit_button("대분류 추가하기"):
                if new_main_name and new_main_name not in menus:
                    menus[new_main_name] = {"type": new_main_type, "subs": []}
                    save_config(menus)
                    safe_rerun()
                else: st.error("오류: 이름 중복 또는 공란")
        st.markdown("---")
        st.subheader("❌ 대분류 삭제")
        with st.form("del_main_form"):
            del_main_name = st.selectbox("삭제할 대분류를 고르세요", list(menus.keys()))
            if st.form_submit_button("선택 삭제", type="primary"):
                del menus[del_main_name]
                save_config(menus)
                safe_rerun()
    with c2:
        if menus:
            st.subheader("➕ 소분류(상단 탭) 추가")
            with st.form("add_sub_form"):
                target_main_conf = st.selectbox("어느 대분류에 추가할까요?", list(menus.keys()))
                new_sub_name = st.text_input("새 소분류 이름")
                if st.form_submit_button("추가하기"):
                    if new_sub_name and new_sub_name not in menus[target_main_conf]["subs"]:
                        menus[target_main_conf]["subs"].append(new_sub_name)
                        save_config(menus)
                        safe_rerun()
            st.markdown("---")
            st.subheader("❌ 소분류(상단 탭) 삭제")
            with st.form("del_sub_form"):
                del_target_main = st.selectbox("대분류 선택", list(menus.keys()), key="dsm")
                if menus[del_target_main]["subs"]:
                    del_sub_name = st.selectbox("삭제할 소분류", menus[del_target_main]["subs"])
                    if st.form_submit_button("선택 삭제", type="primary"):
                        menus[del_target_main]["subs"].remove(del_sub_name)
                        save_config(menus)
                        safe_rerun()

# 🟢 3) 카테고리 리스트 출력 및 라이브 에디터
else:
    st.title(f"📂 {selected_menu}")
    cat_type = menus[selected_menu]["type"]
    sub_tabs = menus[selected_menu]["subs"]
    
    df_current = st.session_state[f"df_{cat_type}"].copy()
    if not df_current.empty and "대분류" in df_current.columns:
        df_current['norm_main'] = df_current['대분류'].apply(normalize_str)
        filtered_main = df_current[df_current['norm_main'] == normalize_str(selected_menu)]
    else: filtered_main = pd.DataFrame()
    
    if not sub_tabs:
        st.info("상단 탭 소분류가 없습니다. 환경설정에서 추가해 주세요.")
    else:
        tabs = st.tabs(sub_tabs)
        for i, tab in enumerate(tabs):
            with tab:
                current_sub = sub_tabs[i]
                st.caption("💡 표를 더블 클릭하여 내용을 즉시 수정하거나 행을 추가하세요. 편집 후 저장 버튼을 꼭 누르세요.")
                
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
                
                # 💡 구글 시트 백엔드와 실시간 연동되는 데이터 에디터
                edited_df = st.data_editor(
                    display_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"editor_{selected_menu}_{current_sub}"
                )
                
                if st.button(f"💾 [{current_sub}] 수정 내역 구글 시트에 실시간 반영", type="primary", key=f"save_{selected_menu}_{current_sub}"):
                    edited_df = edited_df.dropna(how="all")
                    edited_df["대분류"] = selected_menu
                    edited_df["소분류"] = current_sub
                    
                    df_existing = load_data(cat_type)
                    if not df_existing.empty and "대분류" in df_existing.columns:
                        df_existing = df_existing[~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                                                    (df_existing['소분류'].apply(normalize_str) == normalize_str(current_sub)))]
                    
                    df_final = pd.concat([df_existing, edited_df], ignore_index=True).fillna("")
                    save_data(df_final, cat_type)
                    st.success("구글 스프레드시트 클라우드 DB에 안전하게 저장되었습니다!")
                    safe_rerun()
