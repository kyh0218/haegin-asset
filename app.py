import streamlit as st
import pandas as pd
import os
import io
import json
import re

st.set_page_config(page_title="해긴 자산/비품 통합 관리", layout="wide")

# --- 1. 데이터베이스 및 설정 파일 경로 ---
CONFIG_FILE = "menu_config.json"
DB_FILES = {
    "비품": "data_equipment.csv",
    "SW": "data_software.csv",
    "PC": "data_pc.csv"
}

# --- 2. 엑셀 양식 기준 (특수 탭 분리 적용) ---
COLS = {
    "비품": ["대분류", "소분류", "품목", "최종확인 년도", "분류코드", "개수", "관리번호", "자산번호", "제조사", "모델명", "취득일", "취득가", "위치", "세부위치"],
    "SW": ["대분류", "소분류", "구매일자", "사용자", "소속", "이메일", "사용기한", "비고"],
    "PC": ["대분류", "소분류", "사번", "이름", "소속", "관리번호", "입사일", "교체일", "분류", "CPU", "RAM", "VGA", "디스크1", "디스크2", "OS", "구매일자", "금액", "비고"],
    "대여비품": ["대분류", "소분류", "구분", "책상 H-DE", "의자 H-HM", "서랍 H-DR"] # 하이퍼라이즈 전용
}

try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

# --- 3. 유틸리티 함수 ---
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# 텍스트 띄어쓰기 및 앞의 숫자 제거 (매칭 오류 완벽 방지)
def normalize_str(s):
    if pd.isna(s):
        return ""
    s = str(s).strip().replace(" ", "")
    s = re.sub(r'^\d+[\._\s\-]*', '', s)
    return s

def get_expected_cols(main_tab, sub_tab, dtype):
    if normalize_str(sub_tab) == normalize_str("하이퍼라이즈 대여 비품"):
        return COLS["대여비품"]
    return COLS[dtype]

def load_config():
    default_config = {
        "1. 해긴 비품 리스트": {"type": "비품", "subs": ["사무실&회의실", "휴게실 및 기타", "탕비실&카페테리아", "계절용품", "하이퍼라이즈 대여 비품"]},
        "2. PC 관리": {"type": "PC", "subs": ["전체 사용 PC 목록", "잔여재고", "모니터"]},
        "3. SW목록": {"type": "SW", "subs": ["백신", "Office", "Adobe", "3Ds Max", "VS 2022 pro", "Jetbrains&GitHub", "클로드", "업무용 AI 툴", "기타(구독형)", "기타(영구)", "윈도우", "한글&더존"]},
        "4. 보안모듈": {"type": "SW", "subs": ["보안모듈 통합"]},
        "5. 에셋&플러그인": {"type": "SW", "subs": ["에셋&플러그인 통합"]},
        "6. SW 구매내역": {"type": "SW", "subs": ["구매내역 통합"]}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # 하이퍼라이즈 탭이 없다면 강제 추가
                if "1. 해긴 비품 리스트" in saved and "하이퍼라이즈 대여 비품" not in saved["1. 해긴 비품 리스트"]["subs"]:
                    saved["1. 해긴 비품 리스트"]["subs"].append("하이퍼라이즈 대여 비품")
                return saved
        except: pass
    return default_config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def load_data(dtype):
    file_path = DB_FILES[dtype]
    if os.path.exists(file_path):
        try:
            # 특정 열 규격에 얽매이지 않고 저장된 모든 데이터를 불러옵니다. (하이퍼라이즈 등 특수 열 보존)
            return pd.read_csv(file_path, encoding="utf-8-sig").fillna("")
        except: pass
    return pd.DataFrame(columns=COLS[dtype])

def save_data(df, dtype):
    # 빈칸 처리 후 모두 문자열로 변환하여 안전 저장
    df.fillna("").astype(str).to_csv(DB_FILES[dtype], index=False, encoding="utf-8-sig")

# --- 4. 세션 초기화 ---
if "menu_config" not in st.session_state: st.session_state.menu_config = load_config()
if "df_비품" not in st.session_state: st.session_state.df_비품 = load_data("비품")
if "df_SW" not in st.session_state: st.session_state.df_SW = load_data("SW")
if "df_PC" not in st.session_state: st.session_state.df_PC = load_data("PC")

menus = st.session_state.menu_config

# --- 5. 사이드바 메뉴 네비게이션 ---
st.sidebar.title("🏢 해긴 자산 관리")
nav_list = ["📊 통합 대시보드"] + list(menus.keys()) + ["🛠️ 데이터 관리 (수동입력/삭제)", "⚙️ 환경설정 (탭 관리)"]
selected_menu = st.sidebar.radio("이동할 화면 선택:", nav_list)

st.sidebar.markdown("---")

# --- 6. 사이드바 엑셀 다운로드 ---
st.sidebar.header("📁 빈 양식 다운로드")
st.sidebar.caption("※ 이 양식에 데이터를 복사한 후 아래에 업로드하세요.")
dl_type = st.sidebar.selectbox("다운로드할 양식 종류", ["비품", "SW", "PC", "대여비품"])
if st.sidebar.button("📝 선택한 양식 다운로드", type="primary"):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        clean_cols = COLS[dl_type][2:] # 대분류, 소분류는 시스템이 자동 주입하므로 제외
        pd.DataFrame(columns=clean_cols).to_excel(writer, index=False, sheet_name=f'{dl_type}양식')
    st.sidebar.download_button("📥 내 PC에 저장하기", data=buffer.getvalue(), file_name=f"해긴_{dl_type}_입력양식.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.sidebar.markdown("---")

# --- 7. 사이드바 스마트 엑셀 업로드 ---
st.sidebar.header("🔄 스마트 엑셀 업로드")
if menus and not selected_menu.startswith("📊") and not selected_menu.startswith("🛠️") and not selected_menu.startswith("⚙️"):
    # 현재 보고 있는 화면(메뉴)에 바로 업로드 하도록 직관적으로 변경
    target_main = selected_menu
    sub_list = menus[target_main]["subs"] if menus[target_main]["subs"] else ["(소분류 없음)"]
    target_sub = st.sidebar.selectbox("🎯 현재 보고계신 이 탭에 올립니다:", sub_list)
    
    target_type = menus[target_main]["type"]
    expected_cols = get_expected_cols(target_main, target_sub, target_type)
    
    upload_mode = st.sidebar.radio("업로드 방식:", ["현재 탭 데이터만 교체 (안전함)", "현재 탭 아래에 이어붙이기"])
    
    uploaded_file = st.sidebar.file_uploader("엑셀 파일 올리기", type=["xlsx", "csv"])

    if uploaded_file:
        st.sidebar.error("⚠️ 잠시만요! 아래 버튼을 눌러 확정해주세요.")
        if st.sidebar.button("📥 시스템에 최종 적용하기", type="primary", use_container_width=True):
            try:
                if uploaded_file.name.endswith(".xlsx"): df_up = pd.read_excel(uploaded_file)
                else: df_up = pd.read_csv(uploaded_file, encoding="utf-8-sig")
                
                df_up["대분류"] = target_main
                df_up["소분류"] = target_sub
                
                # 지정된 양식(일반 비품 vs 대여 비품)에 맞게 빈 열 보정
                for c in expected_cols:
                    if c not in df_up.columns: df_up[c] = ""
                
                df_up = df_up[expected_cols].fillna("")
                
                df_existing = st.session_state[f"df_{target_type}"].copy()
                if upload_mode == "현재 탭 데이터만 교체 (안전함)":
                    if not df_existing.empty:
                        df_existing = df_existing[
                            ~((df_existing['대분류'].apply(normalize_str) == normalize_str(target_main)) & 
                              (df_existing['소분류'].apply(normalize_str) == normalize_str(target_sub)))
                        ]
                
                df_final = pd.concat([df_existing, df_up], ignore_index=True).fillna("")
                st.session_state[f"df_{target_type}"] = df_final
                save_data(df_final, target_type)
                st.sidebar.success(f"성공! [{target_sub}] 탭에 반영되었습니다.")
                safe_rerun()
            except Exception as e:
                st.sidebar.error(f"오류가 발생했습니다: {e}")

# --- 8. 메인 화면 로직 ---

# 🟢 1) 통합 대시보드
if selected_menu == "📊 통합 대시보드":
    st.title("📦 해긴 자산 통합 대시보드")
    eq_df, sw_df, pc_df = st.session_state.df_비품, st.session_state.df_SW, st.session_state.df_PC
    
    eq_count = pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').sum() if "개수" in eq_df.columns else 0
    eq_val = (pd.to_numeric(eq_df.get("개수", pd.Series()), errors='coerce').fillna(0) * pd.to_numeric(eq_df.get("취득가", pd.Series()), errors='coerce').fillna(0)).sum() if "개수" in eq_df.columns else 0
    
    pc_count = len(pc_df)
    pc_val = pd.to_numeric(pc_df.get("금액", pd.Series()), errors='coerce').sum() if "금액" in pc_df.columns else 0
    sw_count = len(sw_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 전체 비품/기기 수량", f"{int(eq_count + pc_count):,.0f} 개")
    col2.metric("💾 관리 중인 SW 라이선스", f"{sw_count:,.0f} 개")
    col3.metric("💰 비품 & PC 총 자산가치", f"₩ {int(eq_val + pc_val):,.0f}")
    st.markdown("---")
    st.info("왼쪽 메뉴에서 각 카테고리를 클릭하여 상세 리스트를 확인 및 직접 수정하세요.")

# 🟢 2) 탭 관리 (환경설정)
elif selected_menu == "⚙️ 환경설정 (탭 관리)":
    st.title("⚙️ 시스템 카테고리(탭) 관리")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ 대분류 추가")
        with st.form("add_main_form"):
            new_main_name = st.text_input("새 대분류 이름 (예: 7. 차량 관리)")
            new_main_type = st.selectbox("어떤 양식을 적용하시겠습니까?", ["비품", "SW", "PC"])
            if st.form_submit_button("대분류 추가하기"):
                if new_main_name and new_main_name not in menus:
                    menus[new_main_name] = {"type": new_main_type, "subs": []}
                    save_config(menus)
                    st.success("대분류가 추가되었습니다!")
                    safe_rerun()
                else:
                    st.error("이름을 입력하지 않았거나 이미 존재하는 이름입니다.")
                    
        st.markdown("---")
        st.subheader("❌ 대분류 삭제")
        with st.form("del_main_form"):
            del_main_name = st.selectbox("삭제할 대분류를 고르세요", list(menus.keys()))
            if st.form_submit_button("선택 대분류 영구 삭제", type="primary"):
                if del_main_name in menus:
                    del menus[del_main_name]
                    save_config(menus)
                    st.warning("대분류가 삭제되었습니다.")
                    safe_rerun()
    with c2:
        if menus:
            st.subheader("➕ 소분류(상단 탭) 추가")
            with st.form("add_sub_form"):
                target_main_conf = st.selectbox("어느 대분류에 추가할까요?", list(menus.keys()), key="sub_target")
                new_sub_name = st.text_input("새 소분류 이름")
                if st.form_submit_button("소분류 추가하기"):
                    if new_sub_name and new_sub_name not in menus[target_main_conf]["subs"]:
                        menus[target_main_conf]["subs"].append(new_sub_name)
                        save_config(menus)
                        st.success("소분류가 추가되었습니다!")
                        safe_rerun()
                        
            st.markdown("---")
            st.subheader("❌ 소분류(상단 탭) 삭제")
            with st.form("del_sub_form"):
                del_target_main = st.selectbox("대분류 선택", list(menus.keys()), key="del_sub_target")
                if menus[del_target_main]["subs"]:
                    del_sub_name = st.selectbox("삭제할 소분류", menus[del_target_main]["subs"])
                    if st.form_submit_button("소분류 삭제", type="primary"):
                        menus[del_target_main]["subs"].remove(del_sub_name)
                        save_config(menus)
                        st.warning("소분류가 삭제되었습니다.")
                        safe_rerun()
                else:
                    st.info("이 대분류에는 삭제할 소분류가 없습니다.")

# 🟢 3) 수동 데이터 관리 (추가 및 특정 탭 초기화)
elif selected_menu == "🛠️ 데이터 관리 (수동입력/삭제)":
    st.title("🛠️ 데이터 수동 등록 및 초기화")
    if not menus:
        st.warning("환경설정에서 대분류를 먼저 생성해주세요.")
    else:
        tab_manual, tab_clear = st.tabs(["➕ 건별 수동 등록", "🗑️ 특정 탭 데이터 비우기"])
        
        with tab_manual:
            target_main_manual = st.selectbox("등록할 대분류", list(menus.keys()))
            target_sub_manual = st.selectbox("등록할 소분류", menus[target_main_manual]["subs"] if menus[target_main_manual]["subs"] else ["(소분류 없음)"])
            dtype = menus[target_main_manual]["type"]
            expected_cols = get_expected_cols(target_main_manual, target_sub_manual, dtype)
            
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

# 🟢 4) 각 카테고리별 출력 화면 (최종 결과 및 엑셀 에디터)
else:
    st.title(f"📂 {selected_menu}")
    cat_type = menus[selected_menu]["type"]
    sub_tabs = menus[selected_menu]["subs"]
    
    df_current = st.session_state[f"df_{cat_type}"].copy()
    
    # 띄어쓰기 등 미세 오차 무시 로직 적용
    if not df_current.empty and "대분류" in df_current.columns:
        df_current['norm_main'] = df_current['대분류'].apply(normalize_str)
        filtered_main = df_current[df_current['norm_main'] == normalize_str(selected_menu)]
    else:
        filtered_main = pd.DataFrame()
    
    if not sub_tabs:
        st.info("환경설정 메뉴에서 하위 소분류 탭을 먼저 만들어 주세요.")
    else:
        tabs = st.tabs(sub_tabs)
        for i, tab in enumerate(tabs):
            with tab:
                current_sub = sub_tabs[i]
                st.caption("💡 아래 표를 **더블 클릭하여 내용 수정**하거나, 하단 빈 칸을 눌러 데이터를 추가하세요.")
                
                expected_cols = get_expected_cols(selected_menu, current_sub, cat_type)
                display_cols = [c for c in expected_cols if c not in ["대분류", "소분류"]]
                
                if not filtered_main.empty and "소분류" in filtered_main.columns:
                    filtered_main_copy = filtered_main.copy()
                    filtered_main_copy['norm_sub'] = filtered_main_copy['소분류'].apply(normalize_str)
                    filtered_sub = filtered_main_copy[filtered_main_copy['norm_sub'] == normalize_str(current_sub)]
                else:
                    filtered_sub = pd.DataFrame()
                
                # 표에 뿌려줄 컬럼 맞추기 (빈칸 채우기)
                for c in display_cols:
                    if c not in filtered_sub.columns:
                        filtered_sub[c] = ""
                display_df = filtered_sub[display_cols]
                
                # 💡 [핵심] 화면 직접 수정 에디터 바인딩
                edited_df = st.data_editor(
                    display_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"editor_{selected_menu}_{current_sub}"
                )
                
                # 💡 저장 버튼
                if st.button(f"💾 [{current_sub}] 수정 내역 반영 및 저장하기", type="primary", key=f"save_{selected_menu}_{current_sub}"):
                    # 빈 행 제거 후 대분류 소분류 꼬리표 추가
                    edited_df = edited_df.dropna(how="all")
                    edited_df["대분류"] = selected_menu
                    edited_df["소분류"] = current_sub
                    
                    # 기존 원본에서 현재 탭의 데이터만 싹 지우고 방금 수정된 데이터를 병합
                    df_existing = st.session_state[f"df_{cat_type}"].copy()
                    if not df_existing.empty and "대분류" in df_existing.columns:
                        df_existing = df_existing[
                            ~((df_existing['대분류'].apply(normalize_str) == normalize_str(selected_menu)) & 
                              (df_existing['소분류'].apply(normalize_str) == normalize_str(current_sub)))
                        ]
                    
                    df_final = pd.concat([df_existing, edited_df], ignore_index=True).fillna("")
                    st.session_state[f"df_{cat_type}"] = df_final
                    save_data(df_final, cat_type)
                    st.success("데이터가 안전하게 저장되었습니다!")
                    safe_rerun()
