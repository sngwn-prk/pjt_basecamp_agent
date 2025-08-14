# import subprocess
# import sys
# import os

import streamlit as st
import pandas as pd
import time
import base64
import json
# import gspread
# from google.oauth2.service_account import Credentials
# from streamlit_gsheets import GSheetsConnection
from streamlit_option_menu import option_menu

from pages.page_phone_input import page_phone_input
from pages.page_verification import page_verification
from utils.utils_gsheet import read_sheet_by_df, update_sheet_add_row, update_sheet_specific_rows
from utils.util_quiz_agent import quiz_analyzer_english, quiz_analyzer_science
from utils.util_sms_sender import send_sms

# from dotenv import load_dotenv
# load_dotenv()
# DEVELOPER_EMAIL = os.getenv("DEVELOPER_EMAIL")
DEVELOPER_EMAIL = st.secrets["DEVELOPER_EMAIL"]

# # Streamlit 메시지 비활성화
# os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
# os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

WEBAPP_NAME = "BASECAMP Agent"

# # 환경 변수를 확인하여 무한 실행 방지
# if "RUNNING_STREAMLIT" not in os.environ:
#     os.environ["RUNNING_STREAMLIT"] = "1"
#     subprocess.Popen([sys.executable, "-m", "streamlit", "run", sys.argv[0]], close_fds=True)
#     sys.exit(0)

def render_quiz_analyzer(tab_name):
    # 2열 레이아웃 생성
    col1, col2 = st.columns([1, 1], gap="large")

    # 분석 중단 플래그를 세션 상태로 관리 (탭별로 독립적)
    if f"analyzing_{tab_name}" not in st.session_state:
        st.session_state[f"analyzing_{tab_name}"] = False
    if f"analyze_stop_{tab_name}" not in st.session_state:
        st.session_state[f"analyze_stop_{tab_name}"] = False
    
    # 업로드된 이미지 상태를 세션에 저장 (탭별로 독립적)
    if f"uploaded_image_{tab_name}" not in st.session_state:
        st.session_state[f"uploaded_image_{tab_name}"] = None

    with col1:
        st.subheader("1단계: 문제 선택")

        # 이미지 업로드 방법 선택
        upload_method = st.selectbox(
            "이미지 입력 방법을 선택하세요.",
            ["파일 선택", "카메라 촬영"],
            index=0,
            key=f"upload_method_{tab_name}"
        )

        if upload_method == "파일 선택":
            uploaded_image = st.file_uploader(
                "분석 대상 이미지를 업로드하세요.",
                type=['png', 'jpg', 'jpeg'],
                accept_multiple_files=False,
                key=f"file_uploader_{tab_name}"
            )
        else:  # 카메라 촬영
            uploaded_image = st.camera_input(
                "분석 대상 이미지를 촬영하세요.",
                key=f"camera_input_{tab_name}"
            )
        
        # 업로드된 이미지를 세션 상태에 저장
        if uploaded_image is not None:
            st.session_state[f"uploaded_image_{tab_name}"] = uploaded_image

        # 이미지가 업로드된 경우 처리
        if st.session_state[f"uploaded_image_{tab_name}"] is not None:
            st.divider()
            st.subheader("2단계: 문제 확인 및 분석 시작")
            st.image(st.session_state[f"uploaded_image_{tab_name}"], caption="업로드된 문제")

            # 이미지를 base64로 변환
            img_bytes = st.session_state[f"uploaded_image_{tab_name}"].getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

            # 분석 중이 아닐 때: 분석 시작 버튼, 분석 중일 때: 분석 중단 버튼
            if not st.session_state[f"analyzing_{tab_name}"]:
                if st.button("분석 시작", type="primary", use_container_width=True, key=f"start_analyze_{tab_name}"):
                    st.session_state[f"analyzing_{tab_name}"] = True
                    st.session_state[f"analyze_stop_{tab_name}"] = False
                    st.rerun()
            else:
                if st.button("분석 중단", type="secondary", use_container_width=True, key=f"stop_analyze_{tab_name}"):
                    st.session_state[f"analyze_stop_{tab_name}"] = True
                    st.session_state[f"analyzing_{tab_name}"] = False
                    st.info("분석이 중단되었습니다.")
                    st.rerun()

            # 분석 중일 때만 분석 로직 실행
            if st.session_state[f"analyzing_{tab_name}"] and not st.session_state[f"analyze_stop_{tab_name}"]:
                with st.spinner("문제를 분석하고 있습니다...", show_time=True):
                    try:
                        if tab_name == "영어":
                            total_cost, response = quiz_analyzer_english(img_base64)
                        elif tab_name == "과학":
                            total_cost, response = quiz_analyzer_science(img_base64)

                        # 분석 중단 요청이 들어왔는지 확인
                        if st.session_state[f"analyze_stop_{tab_name}"]:
                            st.info("분석이 중단되었습니다.")
                            st.session_state[f"analyzing_{tab_name}"] = False
                            st.rerun()
                        else:
                            if total_cost:
                                # 결과를 세션 상태에 저장 (탭별로 독립적)
                                st.session_state[f"quiz_result_{tab_name}"] = {
                                    'answer': response.get('answer', ''),
                                    'description': response.get('description', ''),
                                    'keywords': response.get('keywords', ''),
                                    'total_cost': total_cost if total_cost is not None else 0,
                                }
                                st.session_state[f"analyzing_{tab_name}"] = False
                                st.session_state[f"last_feedback_uploaded_{tab_name}"] = False
                                st.rerun()
                            else:
                                st.session_state[f"analyzing_{tab_name}"] = False
                                st.error("❌ 문제 분석 중 오류가 발생했습니다. 다시 시도해주세요.")
                    except Exception as e:
                        st.session_state[f"analyzing_{tab_name}"] = False
                        st.error(f"❌ 문제 분석 중 오류가 발생했습니다: {str(e)}")
            st.divider()

    with col2:
        st.subheader("3단계: 분석 결과 확인")
        # 이전 분석 결과가 있는 경우 표시
        if f"quiz_result_{tab_name}" in st.session_state and st.session_state[f"quiz_result_{tab_name}"]:
            quiz_result = st.session_state.get(f"quiz_result_{tab_name}", "")
            st.markdown("##### 분석 결과 예시")
            st.markdown(":red-background[1. 정답]")
            st.markdown(quiz_result.get('answer', ''))
            st.divider()
            st.markdown(":red-background[2. 해설]")
            st.markdown(quiz_result.get('description', ''))
            st.divider()
            st.markdown(":red-background[3. 키워드]")
            st.markdown(quiz_result.get('keywords', ''))
            
            # 사용 기록 업로드
            create_dt = time.strftime("%Y%m%d %H:%M:%S", time.localtime())
            date_partition = create_dt.split(" ")[0]    
            phn_no = st.session_state.get("phone_number", "")
            admin_mode = st.session_state.get("admin_mode", False)
            if admin_mode:
                access_type = "관리자"
            else:
                access_type = "일반(학생)"
            subject = tab_name
            agent_type = "quiz_analyzer"
            total_cost = quiz_result.get('total_cost', 0)
            update_sheet_add_row("tbl_agent_usg_incr", [date_partition, create_dt, phn_no, access_type, subject, agent_type, total_cost])
        else:
            st.markdown("##### 분석 결과 예시")
            st.markdown(":red-background[1. 정답]")
            st.divider()
            st.markdown(":red-background[2. 해설]")
            st.divider()
            st.markdown(":red-background[3. 키워드]")

def page_main():
    """메인 페이지"""
    # 페이지 설정
    st.set_page_config(
        page_title=WEBAPP_NAME,
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 관리자 모드 확인
    admin_mode = st.session_state.get("admin_mode", False)
    
    # 사이드바 구성
    with st.sidebar:
        st.title("📝 BASECAMP Agent")
        
        # 현재 계정 및 권한 상태 표시
        if admin_mode:
            st.badge("관리자", color="red")
        else:
            st.badge("일반(학생)", color="blue")
        phone_number = st.session_state.get("phone_number", "")
        st.write(f"**{phone_number}**")
        
        st.divider()
        
        # 메뉴 구성 - 관리자 모드에 따라 다르게 표시
        menu_options = ["About", "Release Notes", "---", "Quiz Analyzer", "---", "Dashboard"]
        menu_icons = ["bi bi-house", "bi bi-sticky", None, "bi bi-chat", None, "bi bi-bar-chart-line"]
        if admin_mode:
            menu_options += ["---", "Access Control", "Admin Dashboard"]
            menu_icons += [None, "bi bi-key", "bi bi-bar-chart-line"]

        # 현재 선택된 메뉴를 세션 상태로 관리
        if "selected_menu" not in st.session_state:
            st.session_state.selected_menu = "Quiz Analyzer"

        # option_menu를 사용하여 메뉴 표시
        selected_menu = option_menu(
            "Menu", 
            menu_options,
            icons=menu_icons,
            menu_icon="app-indicator", 
            default_index=0,
            styles={
                "icon": {"font-size": "16px"},
                "nav-link": {"font-size": "15px", "text-align": "left", "margin":"0px", "--hover-color": "transparent"},
            }
        )

        # 메뉴 선택 시 세션 상태 업데이트
        if selected_menu != st.session_state.selected_menu:
            st.session_state.selected_menu = selected_menu
            # Admin 메뉴가 선택된 경우 기존 데이터를 삭제하여 새로 불러오도록 함
            if selected_menu == "Access Control":
                if "admin_df" in st.session_state:
                    del st.session_state.admin_df
                if "admin_last_load" in st.session_state:
                    del st.session_state.admin_last_load
            st.rerun()

        st.divider()
        
        # 최하단 로그아웃 버튼 - 고정 위치
        if st.button("Logout", key="logout_button", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.step = "phone_input"  # 초기화면으로 돌아가기
            st.session_state.phone_number = ""
            st.session_state.verification_code = ""
            st.session_state.sent_code = ""
            st.session_state.code_sent_time = None
            st.session_state.admin_mode = False  # 관리자 모드도 초기화
            st.rerun()
    
    # 메인 컨텐츠 영역
    selected_menu = st.session_state.selected_menu
    
    if selected_menu == "About":
        st.title("About")
        try:
            with open("README.md", "r", encoding="utf-8") as f:
                about_content = f.read()
            st.markdown(about_content)
            st.markdown(f"- Email: {DEVELOPER_EMAIL}")
        except FileNotFoundError:
            st.error("README.md 파일을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {str(e)}")
    
    elif selected_menu == "Release Notes":
        st.title("Release Notes")
        st.write("최신 업데이트 내용과 변경사항을 확인할 수 있습니다.")
        try:
            with open("ReleaseNote.md", "r", encoding="utf-8") as f:
                release_notes_content = f.read()
            st.markdown(release_notes_content)
        except FileNotFoundError:
            st.error("ReleaseNote.md 파일을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {str(e)}")

    elif selected_menu == "Quiz Analyzer":
        st.title("Quiz Analyzer")
        st.markdown(
            """
            - 업로드된 문제(이미지)를 AI를 통해 분석하여 문제의 정답과 해설을 제공합니다.
            - 생성된 결과에 대한 피드백을 남겨주세요. 피드백은 향후 기능 개선에 활용됩니다.
            - AI가 생성한 정보는 오류를 포함할 수 있기 때문에 참고용으로만 사용해주세요.

            :red-background[1단계: 문제 선택]
            - 문제는 사진 업로드 또는 사진 촬영을 통해 업로드 가능합니다. (PNG, JPG, JPEG / 0MB 이하)

            :red-background[2단계: 문제 확인 및 분석 시작]
            - 업로드한 문제를 확인할 수 있으며, 분석 시작을 통해 AI 분석을 실행합니다.
            - 분석 중단을 누르면 분석이 중단됩니다.

            :red-background[3단계: 분석 결과 확인]
            - AI가 문제를 분석한 결과를 확인합니다.
            - 새로운 문제를 분석하고자 할 때는 1단계로 돌아가 새로운 문제를 업로드해주세요.
            """
        )
        tab1, tab2, tab3, tab4 = st.tabs(["국어", "수학", "영어", "과학"])
        with tab1:
            st.write("Coming soon...")
        with tab2:
            st.write("Coming soon...")
        with tab3:
            render_quiz_analyzer("영어")
        with tab4:
            render_quiz_analyzer("과학")

    elif selected_menu == "Dashboard":
        st.title("Dashboard")
        st.markdown(
            """
            - 나의 Agent 사용 기록을 확인할 수 있습니다.
            """
        )

        if admin_mode:
            admin_mode = "관리자"
        else:
            admin_mode = "일반(학생)"
        phone_number = st.session_state.get("phone_number", "")

        df_log = read_sheet_by_df("tbl_agent_usg_incr")
        df_log = df_log[(df_log['phn_no'] == phone_number) & (df_log['access_type'] == admin_mode)]
                
        df_name = read_sheet_by_df("tbl_mbr_req_incr")
        df_name = df_name[(df_name['phn_no'] == phone_number) & (df_name['access_type'] == admin_mode)]
        df_name = df_name[['phn_no', 'name']].drop_duplicates()
        df_log = df_log.merge(df_name, on='phn_no', how='left')

        if not df_log.empty:
            # 컬럼명을 한글로 매핑 (필요시)
            column_mapping = {
                'date_partition': '날짜',
                'create_dt': '날짜/시간',
                'name': '이름',
                'phn_no': '연락처',
                'access_type': '권한 유형',
                'subject': '과목',
                'agent_type': 'Agent 유형',
                'total_cost': '발생 비용'
            }
            df_log_renamed = df_log[['date_partition', 'create_dt', 'name', 'phn_no', 'access_type', 'subject', 'agent_type', 'total_cost']]
            df_log_renamed = df_log_renamed.rename(columns=column_mapping)
            st.dataframe(df_log_renamed, use_container_width=True)

    elif selected_menu == "Access Control" and  admin_mode==True:
        st.title("Access Control")
        st.markdown(
            """
            - 사용자들의 권한을 관리할 수 있는 관리자 전용 페이지입니다.

            :red-background[권한 관리]
            - **권한 상태**의 값을 아래와 같이 변경하여 사용자의 권한을 관리할 수 있습니다. 그 외의 값들은 변경이 불가합니다.
                1) 활성: 사용자가 권한을 획득한 상태
                2) 대기: 관리자가 권한 요청을 검토 중인 상태
                3) 비활성: 관리자가 권한 요청을 거절한 상태

            :red-background[권한 수정 이력]
            - 권한 관리 탭에서 변경한 권한 수정 이력을 확인할 수 있습니다. (읽기 전용)
            """
        )
        tab1, tab2 = st.tabs(["권한 관리", "권한 수정 이력"])
        with tab1:
            try:
                # 세션 상태에 데이터가 없거나 Admin 메뉴에 처음 접근한 경우에만 데이터를 불러옴
                if "admin_df" not in st.session_state or "admin_last_load" not in st.session_state:
                    st.session_state.admin_df = read_sheet_by_df("tbl_mbr_req_incr")
                    st.session_state.admin_last_load = time.time()
                
                df = st.session_state.admin_df

                if not df.empty:
                    df_display = df.copy()
                    
                    # 컬럼 이름을 한글로 변경 (표시용)
                    column_mapping = {
                        'req_id': '요청ID',
                        'date_partition': '날짜',
                        'create_dt': '날짜/시간',
                        'name': '이름',
                        'phn_no': '연락처',
                        'access_type': '권한 유형',
                        'agr_svc_terms': '이용약관동의',
                        'agr_psnl_info': '개인정보수집이용동의',
                        'status': '권한 상태'
                    }
                    
                    # 표시용 데이터프레임의 컬럼 이름 변경
                    df_display_renamed = df_display.rename(columns=column_mapping)
                    
                    # 필터링 기능 추가 - 데이터프레임 우측 상단에 배치
                    filter_options = ["전체", "활성", "대기", "비활성"]
                    selected_filter = st.segmented_control(
                        "필터",
                        options=filter_options,
                        default="전체",
                        key="status_filter"
                    )
                    
                    # 필터링 적용
                    if selected_filter != "전체":
                        df_display_renamed = df_display_renamed[df_display_renamed['권한 상태'] == selected_filter]
                    
                    # 편집 가능한 데이터프레임 표시 (한글 컬럼명 사용)
                    edited_df_renamed = st.data_editor(
                        df_display_renamed,
                        use_container_width=True,
                        num_rows="fixed",
                        key="permission_editor",
                        disabled=["요청ID", "날짜", "날짜/시간", "이름", "연락처", "권한 유형", "이용약관동의", "개인정보수집이용동의"],
                    )
                    
                    # 한글 컬럼명을 다시 영문으로 변환 (저장용)
                    reverse_mapping = {v: k for k, v in column_mapping.items()}
                    edited_df = edited_df_renamed.rename(columns=reverse_mapping)
                    
                    # status 컬럼의 값이 올바른지 확인 (실시간 검증)
                    invalid_status = edited_df[~edited_df['status'].isin(['활성', '대기', '비활성'])]
                    
                    # 실시간 경고 메시지 표시
                    if not invalid_status.empty:
                        st.session_state.admin_message = {"type": "warning", "text": "⚠️ 권한 상태 컬럼에는 '활성', '대기', '비활성' 중 하나만 입력 가능합니다."}
                    elif "admin_message" in st.session_state and st.session_state.admin_message.get("type") == "warning":
                        # 잘못된 값이 수정되었으면 warning 메시지 제거
                        del st.session_state.admin_message
                    
                    # 저장 버튼
                    if st.button("변경사항 적용", use_container_width=True):
                        try:
                            # status 컬럼의 값이 올바른지 확인
                            if not invalid_status.empty:
                                st.session_state.admin_message = {"type": "error", "text": "❌ 권한 상태 컬럼에는 '활성', '대기', '비활성' 중 하나만 입력 가능합니다."}
                                st.rerun()
                            
                            # 변경사항이 있는지 확인
                            if not edited_df.equals(df_display):
                                # 원본 데이터프레임에 변경사항 적용 (req_id를 기준으로 매핑)
                                updated_df = df.copy()
                                
                                # 상태 변경 추적을 위한 딕셔너리 생성
                                status_changes = []
                                
                                # 편집된 데이터프레임의 각 행에 대해 원본 데이터프레임에서 해당 req_id를 찾아 업데이트
                                for _, edited_row in edited_df.iterrows():
                                    req_id = edited_row.get('req_id')
                                    if req_id is not None:
                                        # 원본 데이터프레임에서 해당 req_id를 가진 행 찾기
                                        original_idx = updated_df[updated_df['req_id'] == req_id].index
                                        if len(original_idx) > 0:
                                            # 상태 변경 추적
                                            original_status = df.loc[df['req_id'] == req_id, 'status'].values[0]
                                            new_status = edited_row['status']
                                            phn_no = df.loc[df['req_id'] == req_id, 'phn_no'].values[0]
                                            access_type = df.loc[df['req_id'] == req_id, 'access_type'].values[0]
                                            if original_status != new_status:
                                                status_changes.append({
                                                    "req_id": req_id,
                                                    "phn_no": phn_no,
                                                    "access_type": access_type,
                                                    "from": original_status,
                                                    "to": new_status
                                                })
                                            # 해당 행의 모든 컬럼 업데이트
                                            for col in edited_df.columns:
                                                if col in updated_df.columns and col not in ['req_id', 'date_partition', 'create_dt', 'access_type', 'agr_svc_terms', 'agr_psnl_info']:
                                                    updated_df.loc[original_idx[0], col] = edited_row[col]
                                
                                # 문자 발송 대상 연락처 추출
                                for change in status_changes:
                                    if change['from'] in ['대기', '비활성'] and change['to'] == '활성':
                                        sms_body = f"[BASECAMP Agent]\n접근 권한이 활성화되었습니다."
                                        sms_type = "approved"
                                    elif change['from'] == '활성' and change['to'] in ['대기', '비활성']:
                                        sms_body = f"[BASECAMP Agent]\n접근 권한이 비활성화되었습니다."
                                        sms_type = "rejected"
                                    else:
                                        continue

                                    create_dt = time.strftime("%Y%m%d %H:%M:%S", time.localtime())
                                    date_partition = create_dt.split(" ")[0]    
                                    send_sms(date_partition, create_dt, change['phn_no'], sms_type, sms_body)

                                    phn_no_author = st.session_state.get("phone_number", "")
                                    update_sheet_add_row(
                                        "tbl_mbr_access_chg_incr", 
                                        [
                                            change['req_id'], date_partition, create_dt, change['phn_no'], change['access_type'], phn_no_author, change['from'], change['to']
                                        ]
                                    )
                                    time.sleep(0.1)
                                
                                # 변경된 행만 업데이트
                                success, _ = update_sheet_specific_rows("tbl_mbr_req_incr", df, updated_df)
                                if success:
                                    st.session_state.admin_message = {"type": "success", "text": f"✅ 변경사항을 성공적으로 적용하였습니다."}
                                    # 저장 후 세션 상태의 데이터도 업데이트
                                    st.session_state.admin_df = updated_df
                                    st.session_state.admin_last_load = time.time()
                                    st.rerun()
                                else:
                                    st.session_state.admin_message = {"type": "error", "text": "❌ 변경사항 적용에 실패했습니다."}
                                    st.rerun()
                            else:
                                st.session_state.admin_message = {"type": "info", "text": "ℹ️ 변경사항이 없습니다."}
                                st.rerun()
                        except Exception as e:
                            st.session_state.admin_message = {"type": "error", "text": f"❌ 변경사항 적용 중 오류가 발생했습니다: {e}"}
                            st.rerun()
                    
                    # 메시지 표시 (변경사항 적용 버튼 하단)
                    if "admin_message" in st.session_state and st.session_state.admin_message:
                        message_type = st.session_state.admin_message["type"]
                        message_text = st.session_state.admin_message["text"]
                        
                        if message_type == "success":
                            st.success(message_text)
                        elif message_type == "error":
                            st.error(message_text)
                        elif message_type == "warning":
                            st.warning(message_text)
                        elif message_type == "info":
                            st.info(message_text)
                        
                        # 메시지 표시 후 세션에서 제거 (다음 페이지 로드 시에는 표시하지 않음)
                        # 단, warning 메시지는 실시간 검증을 위해 유지
                        if message_type != "warning":
                            del st.session_state.admin_message
                else:
                    st.info("데이터가 없습니다.")
                    
            except Exception as e:
                st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
                st.code(f"오류 상세: {str(e)}")
        with tab2:
            try:
                df_access_chg = read_sheet_by_df("tbl_mbr_access_chg_incr")
                
                df_name = read_sheet_by_df("tbl_mbr_req_incr")
                df_name = df_name[['phn_no', 'name']].drop_duplicates()
                df_access_chg = df_access_chg.merge(df_name, on='phn_no', how='left')

                if not df_access_chg.empty:
                    # 컬럼명을 한글로 매핑 (필요시)
                    column_mapping = {
                        'req_id': '요청ID',
                        'date_partition': '날짜',
                        'create_dt': '날짜/시간',
                        'name': '이름',
                        'phn_no': '연락처',
                        'access_type': '권한 유형',
                        'author': '관리자 연락처',
                        'status_from': '기존 권한',
                        'status_to': '신규 권한'
                    }
                    df_access_chg_renamed = df_access_chg[['req_id', 'date_partition', 'create_dt', 'name', 'phn_no', 'access_type', 'author', 'status_from', 'status_to']]
                    df_access_chg_renamed = df_access_chg_renamed.rename(columns=column_mapping)
                    st.dataframe(df_access_chg_renamed, use_container_width=True)
                else:
                    st.info("권한 변경 이력 데이터가 없습니다.")
            except Exception as e:
                st.error(f"권한 변경 이력 데이터를 불러오는 중 오류가 발생했습니다: {e}")
                st.code(f"오류 상세: {str(e)}")

    elif selected_menu == "Admin Dashboard" and admin_mode==True:
        st.title("Admin Dashboard")
        st.markdown(
            """
            관리자 전용 대시보드입니다.

            :red-background[로그인 이력]
            - 사용자들의 로그인 이력을 확인할 수 있습니다. (읽기 전용)

            :red-background[Agent 사용 이력]
            - 사용자들의 Agent 사용 이력을 확인할 수 있습니다. (읽기 전용)
            """
        )

        tab1, tab2 = st.tabs(["로그인 이력", "Agent 사용 이력"])
        with tab1:
            try:
                df_login = read_sheet_by_df("tbl_mbr_login_incr")

                df_name = read_sheet_by_df("tbl_mbr_req_incr")
                df_name = df_name[['phn_no', 'name']].drop_duplicates()
                df_login = df_login.merge(df_name, on='phn_no', how='left')

                if not df_login.empty:
                    # 컬럼명을 한글로 매핑 (필요시)
                    column_mapping = {
                        'date_partition': '날짜',
                        'create_dt': '날짜/시간',
                        'name':'이름',
                        'phn_no': '연락처',
                        'access_type': '권한 유형',
                    }
                    df_login_renamed = df_login[['date_partition', 'create_dt', 'name', 'phn_no', 'access_type']]
                    df_login_renamed = df_login_renamed.rename(columns=column_mapping)
                    st.dataframe(df_login_renamed, use_container_width=True)
                else:
                    st.info("로그인 이력 데이터가 없습니다.")
            except Exception as e:
                st.error(f"로그인 이력 데이터를 불러오는 중 오류가 발생했습니다: {e}")
                st.code(f"오류 상세: {str(e)}")
        with tab2:
            try:
                df_log = read_sheet_by_df("tbl_agent_usg_incr")
                        
                df_name = read_sheet_by_df("tbl_mbr_req_incr")
                df_name = df_name[['phn_no', 'name']].drop_duplicates()
                df_log = df_log.merge(df_name, on='phn_no', how='left')

                if not df_log.empty:
                    # 컬럼명을 한글로 매핑 (필요시)
                    column_mapping = {
                        'date_partition': '날짜',
                        'create_dt': '날짜/시간',
                        'name': '이름',
                        'phn_no': '연락처',
                        'access_type': '권한 유형',
                        'subject': '과목',
                        'agent_type': 'Agent 유형',
                        'total_cost': '발생 비용'
                    }
                    df_log_renamed = df_log[['date_partition', 'create_dt', 'name', 'phn_no', 'access_type', 'subject', 'agent_type', 'total_cost']]
                    df_log_renamed = df_log_renamed.rename(columns=column_mapping)
                    st.dataframe(df_log_renamed, use_container_width=True)
            except Exception as e:
                st.error(f"사용 이력 데이터를 불러오는 중 오류가 발생했습니다: {e}")
                st.code(f"오류 상세: {str(e)}")

def main():
    # 세션 상태 초기화
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "step" not in st.session_state:
        st.session_state.step = "phone_input"  # phone_input, verification, main
    
    if st.session_state.logged_in:
        page_main()
    elif st.session_state.step == "phone_input":
        page_phone_input()
    elif st.session_state.step == "verification":
        page_verification()

if __name__ == "__main__":
    main()
