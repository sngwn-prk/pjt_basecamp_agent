import streamlit as st
import time
from utils.util_sms_sender import send_sms, generate_verification_code

WEBAPP_NAME = "BASECAMP Agent"

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
