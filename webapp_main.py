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

from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser, OutputFixingParser
from langchain_core.messages import HumanMessage
from langchain_community.callbacks import get_openai_callback

from utils.util_sms_sender import send_sms, generate_verification_code
from utils.util_gsheet_editer import get_sheet_df, update_sheet_data_partial, is_registered_user

# from dotenv import load_dotenv
# load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

llm_4o_mini = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o-mini",
    max_tokens=4096,
    temperature=0,
    max_retries=2,
)

llm_o3 = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="o3",
    max_tokens=4096,
    timeout=None,
    max_retries=2,
)

# # Streamlit 환영 메시지 비활성화
# os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
# os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

WEBAPP_NAME = "BASECAMP Agent"

# # 환경 변수를 확인하여 무한 실행 방지
# if "RUNNING_STREAMLIT" not in os.environ:
#     os.environ["RUNNING_STREAMLIT"] = "1"
#     subprocess.Popen([sys.executable, "-m", "streamlit", "run", sys.argv[0]], close_fds=True)
#     sys.exit(0)

def quiz_analyzer_science(img_input_base64):
    response_schemas = [
        ResponseSchema(
            name="answer", 
            description="The answer for the given problem"
        ),
        ResponseSchema(
            name="description", 
            description="The solution process for the given problem"),
        ResponseSchema(
            name="keywords", 
            description="The keywords of scientific concepts that you need to know to solve the given problem. If there are two or more keywords for the problem, separate them with commas (,) and output a maximum of three."
        )
    ]
    parser = StructuredOutputParser.from_response_schemas(response_schemas)
    output_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_4o_mini)
    format_instructions = output_parser.get_format_instructions()

    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"""
                # Role
                Your role is to output the answer(answer), the solution process (description), and the keywords needed to solve a given South Korean high school-level science problem (Image).
                - Answer: Provide the correct answer to the problem.
                - Description: Offer a detailed explanation of the solution process.
                - Keywords: List important terms or concepts necessary for solving the problem.

                # Instructions
                1. Answer according to the given output format (# OutputFormat). 
                If the problem cannot be solved, output 'None' for answer, description, and keywords.
                2. Only consider the environment defined within the problem itself.
                Do not assume facts or logic that go beyond what is provided.
                3. The solution process must be explained in detail at a level understandable to high school students.
                4. The answer must be given in Korean.
                5. For multiple-choice questions, do not alter the order or content of the answer choices; output the choice numbers and contents exactly as shown in the problem. 
                For short-answer questions, output the exact answer.
                
                # OutputFormat: {format_instructions}
                """
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_input_base64}"
                }
            }
        ]
    )
    chain = llm_o3 | output_parser

    try:
        with get_openai_callback() as cb:
            response = chain.invoke([message])
        usage_tokens = cb.total_tokens
        return usage_tokens, response
    except Exception as e:
        print(f"Error: {e}")
        return None, None

def page_main():
    """메인 페이지"""
    # 페이지 설정
    st.set_page_config(
        page_title=WEBAPP_NAME,
        page_icon="🏕️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 관리자 모드 확인
    admin_mode = st.session_state.get("admin_mode", False)
    
    # 사이드바 구성
    with st.sidebar:
        st.title("🏕️ BASECAMP Agent")
        
        # 현재 계정 및 권한 상태 표시
        if admin_mode:
            st.badge("관리자", color="red")
        else:
            st.badge("일반(학생)", color="blue")
        phone_number = st.session_state.get("phone_number", "")
        st.write(f"**{phone_number}**")
        
        st.divider()
        
        # 메뉴 구성 - 관리자 모드에 따라 다르게 표시
        if admin_mode:
            menu_options = ["About", "Release Notes", "Science Agent", "Access Control"]
            menu_icons = ["bi bi-house", "bi bi-sticky", "bi bi-chat", "bi bi-key"]
        else:
            menu_options = ["About", "Release Notes", "Science Agent"]
            menu_icons = ["bi bi-house", "bi bi-sticky", "bi bi-chat"]

        # 현재 선택된 메뉴를 세션 상태로 관리
        if "selected_menu" not in st.session_state:
            st.session_state.selected_menu = "Science Agent"

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
    
    if selected_menu == "Science Agent":
        render_quiz_agent()
        
    elif selected_menu == "Access Control":
        if admin_mode:
            st.title("Access Control")
            st.write(
                """
                - 사용자들의 권한을 관리할 수 있는 관리자 전용 페이지입니다.
                - "권한 상태"의 값을 아래와 같이 변경하여 사용자의 권한을 관리할 수 있습니다.
                    1) 활성: 사용자가 권한을 획득한 상태
                    2) 대기: 관리자가 권한 요청을 검토 중인 상태
                    3) 비활성: 관리자가 권한 요청을 거절한 상태
                - 그 외의 값들은 변경이 불가합니다.
                """
            )
            
            try:
                # 세션 상태에 데이터가 없거나 Admin 메뉴에 처음 접근한 경우에만 데이터를 불러옴
                if "admin_df" not in st.session_state or "admin_last_load" not in st.session_state:
                    st.session_state.admin_df = get_sheet_df("tbl_mbr_req_incr")
                    st.session_state.admin_last_load = time.time()
                
                df = st.session_state.admin_df

                if not df.empty:
                    df_display = df.copy()
                    # df_display['phn_no'] = df_display['phn_no'].apply(format_phone_number)
                    
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
                                
                                # 편집된 데이터프레임의 각 행에 대해 원본 데이터프레임에서 해당 req_id를 찾아 업데이트
                                for _, edited_row in edited_df.iterrows():
                                    req_id = edited_row.get('req_id')
                                    if req_id is not None:
                                        # 원본 데이터프레임에서 해당 req_id를 가진 행 찾기
                                        original_idx = updated_df[updated_df['req_id'] == req_id].index
                                        if len(original_idx) > 0:
                                            # 해당 행의 모든 컬럼 업데이트
                                            for col in edited_df.columns:
                                                if col in updated_df.columns and col not in ['req_id', 'date_partition', 'create_dt', 'access_type', 'agr_svc_terms', 'agr_psnl_info']:
                                                    updated_df.loc[original_idx[0], col] = edited_row[col]
                                
                                # 변경된 행만 업데이트
                                success, _ = update_sheet_data_partial("tbl_mbr_req_incr", df, updated_df)
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
        else:
            st.error("❌ 관리자 권한이 필요합니다.")
            st.info("관리자 모드로 로그인해주세요.")

def page_phone_input():
    """핸드폰 번호 입력 페이지"""
    # 페이지 설정
    st.set_page_config(
        page_title=WEBAPP_NAME,
        page_icon="🏕️",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # 헤더
    st.title("🏕️ BASECAMP Agent")
    st.subheader("📱 휴대폰 번호")
    
    # 관리자 모드 토글 버튼 - 우측 상단에 배치
    col1, col2 = st.columns([5, 1])
    with col1:
        st.write("")  # 빈 공간으로 정렬
    with col2:
        admin_mode = st.toggle(
            "Admin",
            value=st.session_state.get("admin_mode", False),
            help="관리자 모드로 로그인하려면 토글을 활성화하세요."
        )
        st.session_state.admin_mode = admin_mode
    
    # 메인 컨테이너
    with st.container():
        phone_number = st.text_input(
            "숫자만 입력하세요. ('-' 제외)",
            value=st.session_state.get("phone_number", ""),
            placeholder="01012345678",
            help="하이픈(-) 없이 숫자만 입력하세요. 관리자를 통해 사전에 등록된 사용자만 접근 가능합니다."
        )
        phone_number = phone_number.replace('-', '').replace(' ', '')
        
        # 인증번호 발송 버튼
        if st.button("인증번호 발송", use_container_width=True):
            if admin_mode:
                user_status = is_registered_user(phone_number, 'admin')
            else:
                user_status = is_registered_user(phone_number, 'normal')

            if user_status == 'active':
                # 인증번호 생성 및 발송
                cert_code = generate_verification_code()
                st.session_state.sent_code = cert_code
                st.session_state.code_sent_time = time.time()
                st.session_state.phone_number = phone_number
                st.session_state.admin_mode = admin_mode  # 토글 상태에 따라 설정
                
                # SMS 발송
                try:
                    result = send_sms(phone_number, cert_code)
                    if result.get('statusCode') == '202':
                        st.session_state.step = "verification"
                        time.sleep(0.1)
                        st.rerun()
                    else:
                        st.error("❌ SMS 발송에 실패했습니다.")
                except Exception as e:
                    st.warning(f"⚠️ SMS 발송 중 오류 발생. 관리자에게 문의하세요. (오류 내용: {e})")
            elif user_status == 'waiting':
                st.error("❌ 관리자가 권한 요청을 검토 중입니다.")
            else:
                st.error("❌ 등록되지 않은 번호입니다. 아래 링크를 통해 권한을 요청하세요.")
    
    # 하단 정보
    st.divider()
    st.caption("처음 방문하신가요? 관리자에게 권한을 요청하세요. (→ [권한 요청](https://docs.google.com/forms/d/e/1FAIpQLSeQcWnJ9zs_1GiEfoc5aSti28C1s_KpUvWz6r68leTWYGWJ5g/viewform?usp=sharing&ouid=115246951916721958693))")
    st.caption("© 2025 BASECAMP Agent. All rights reserved.")

def page_verification():
    """인증번호 입력 페이지"""
    # 페이지 설정
    st.set_page_config(
        page_title=WEBAPP_NAME,
        page_icon="🏕️",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # 헤더
    st.title("🏕️ BASECAMP Agent")
    st.subheader("🔐 인증번호")

    # 메시지 표시를 위한 세션 상태 초기화
    if "verification_message" not in st.session_state:
        st.session_state.verification_message = {"type": None, "text": ""}
    
    # 메인 컨테이너
    with st.container():
        verification_code = st.text_input(
            "입력하신 휴대폰 번호로 발송된 인증번호를 입력해주세요. (유효시간 30초)",
            value=st.session_state.get("verification_code", ""),
            type="password"
        )
        
        # 로그인 버튼 (상단)
        if st.button("로그인", use_container_width=True):
            elapsed_time = time.time() - st.session_state.code_sent_time
            if elapsed_time <= 30:  # 30초 이내                        
                if verification_code == st.session_state.sent_code:
                    st.session_state.verification_code = verification_code
                    st.session_state.logged_in = True # 메인 페이지로 이동
                    time.sleep(0.1)
                    st.rerun()
                else:
                    st.session_state.verification_message = {"type": "error", "text": "❌ 인증번호가 일치하지 않습니다."}
                    time.sleep(0.1)
                    st.rerun()
            else:
                st.session_state.verification_message = {"type": "error", "text": "❌ 인증번호 유효시간이 만료되었습니다. 인증번호를 재발송해주세요."}
                time.sleep(0.1)
                st.rerun()
        
        # 재발송 버튼 (로그인 아래)
        if st.button("재발송", use_container_width=True):
            phone_number = st.session_state.get("phone_number", "")
            if phone_number:
                # 새로운 인증번호 생성 및 발송
                cert_code = generate_verification_code()
                st.session_state.sent_code = cert_code
                st.session_state.code_sent_time = time.time()
                st.session_state.verification_code = ""  # 입력값 초기화
                
                # SMS 발송
                try:
                    result = send_sms(phone_number, cert_code)
                    if result.get('statusCode') == '202':
                        st.session_state.verification_message = {"type": "success", "text": "✅ 인증번호가 재발송되었습니다."}
                        time.sleep(0.1)
                        st.rerun()
                    else:
                        st.session_state.verification_message = {"type": "error", "text": "❌ SMS 발송에 실패했습니다."}
                        time.sleep(0.1)
                        st.rerun()
                except Exception as e:
                    st.session_state.verification_message = {"type": "warning", "text": f"⚠️ SMS 발송 중 오류 발생. 관리자에게 문의하세요. (오류 내용: {e})"}
                    time.sleep(0.1)
                    st.rerun()
        
        # 이전 페이지 버튼 (재발송 아래)
        if st.button("이전 페이지", use_container_width=True):
            st.session_state.step = "phone_input"
            st.session_state.phone_number = ""
            st.session_state.verification_code = ""
            st.session_state.sent_code = ""
            st.session_state.code_sent_time = None
            st.session_state.verification_message = {"type": None, "text": ""}
            st.session_state.admin_mode = False  # 관리자 모드도 초기화
            time.sleep(0.1)
            st.rerun()
        
        # 최하단 메시지 표시 영역 (이전 페이지 버튼 아래)
        if st.session_state.verification_message["type"]:
            message_type = st.session_state.verification_message["type"]
            message_text = st.session_state.verification_message["text"]
            
            if message_type == "success":
                st.success(message_text)
            elif message_type == "error":
                st.error(message_text)
            elif message_type == "warning":
                st.warning(message_text)
            elif message_type == "info":
                st.info(message_text)
    
    # 하단 정보
    st.divider()
    st.caption("© 2025 BASECAMP Agent. All rights reserved.")

def render_quiz_agent():
    """Science Agent 페이지 렌더링"""
    st.title("Science Agent")
    st.write("과학 문제 이미지를 업로드하거나 촬영하여 답변을 받아보세요.")
    
    # 2열 레이아웃 생성
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("이미지 입력")
        
        # 이미지 업로드 방법 선택
        upload_method = st.radio(
            "이미지 입력 방법을 선택하세요:",
            ["📁 사진 업로드", "📷 카메라 촬영"],
            horizontal=True
        )
        
        uploaded_image = None
        
        if upload_method == "📁 사진 업로드":
            uploaded_image = st.file_uploader(
                "과학 문제 이미지를 업로드하세요",
                type=['png', 'jpg', 'jpeg'],
                help="PNG, JPG, JPEG 형식의 이미지를 업로드할 수 있습니다."
            )
        else:  # 카메라 촬영
            uploaded_image = st.camera_input(
                "과학 문제를 촬영하세요",
                help="카메라로 과학 문제를 촬영하여 업로드할 수 있습니다."
            )
        
        # 이미지가 업로드된 경우 처리
        if uploaded_image is not None:
            # 이미지 표시 (폭 300으로 설정)
            st.subheader("업로드된 이미지")
            st.image(uploaded_image, caption="업로드된 과학 문제", width=300)
            
            # 이미지를 base64로 변환
            img_bytes = uploaded_image.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # 분석 버튼
            if st.button("문제 분석하기", type="primary", use_container_width=True):
                with st.spinner("문제를 분석하고 있습니다..."):
                    try:
                        # quiz_analyzer_science 함수 호출
                        usage_tokens, response = quiz_analyzer_science(img_base64)
                        
                        if response and usage_tokens:
                            # 결과를 세션 상태에 저장
                            st.session_state.quiz_result = {
                                'answer': response.get('answer', ''),
                                'description': response.get('description', ''),
                                'keywords': response.get('keywords', ''),
                                'usage_tokens': usage_tokens
                            }
                            st.rerun()
                        else:
                            st.error("❌ 문제 분석 중 오류가 발생했습니다. 다시 시도해주세요.")
                            
                    except Exception as e:
                        st.error(f"❌ 문제 분석 중 오류가 발생했습니다: {str(e)}")
    
    with col2:
        st.subheader("AI 분석 결과")
        
        # 이전 분석 결과가 있는 경우 표시
        if "quiz_result" in st.session_state and st.session_state.quiz_result:
            display_quiz_result(st.session_state.quiz_result)
        else:
            st.info("👈 왼쪽에서 이미지를 업로드하고 분석 버튼을 클릭하세요.")
            st.markdown("---")
            st.markdown("### 분석 결과 예시")
            st.markdown("""
            **🎯 정답**: 문제의 정답이 여기에 표시됩니다.
            
            **📝 해설**: 상세한 해설 과정이 여기에 표시됩니다.
            
            **🔑 핵심 키워드**: 
            - 키워드1
            - 키워드2
            - 키워드3
            
            **📈 토큰 사용량**: 사용된 토큰 수가 여기에 표시됩니다.
            """)

def display_quiz_result(result):
    """퀴즈 분석 결과 표시"""
    # 결과를 마크다운 형태로 표시
    st.markdown("---")
    
    # 정답 섹션
    st.markdown("### 🎯 정답")
    if result['answer'] and result['answer'] != 'None':
        st.success(f"**{result['answer']}**")
    else:
        st.warning("문제를 해결할 수 없습니다.")
    
    # st.markdown("---")
    
    # 해설 섹션
    st.markdown("### 📝 해설")
    if result['description'] and result['description'] != 'None':
        st.markdown(result['description'])
    else:
        st.info("해설을 제공할 수 없습니다.")
    
    # st.markdown("---")
    
    # 키워드 섹션
    st.markdown("### 🔑 핵심 키워드")
    if result['keywords'] and result['keywords'] != 'None':
        keywords_list = [kw.strip() for kw in result['keywords'].split(',')]
        for keyword in keywords_list:
            st.markdown(f"- **{keyword}**")
    else:
        st.info("키워드를 추출할 수 없습니다.")
    
    # st.markdown("---")
    
    # 사용량 섹션
    st.markdown("### 📈 토큰 사용량")
    st.metric("사용된 토큰", f"{result['usage_tokens']:,}")
    
    # st.markdown("---")
    
    # 새로운 분석을 위한 초기화 버튼
    if st.button("🔄 새로운 분석 시작", use_container_width=True):
        if "quiz_result" in st.session_state:
            del st.session_state.quiz_result
        st.rerun()

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
