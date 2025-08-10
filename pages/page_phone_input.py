import streamlit as st
import time
from utils.util_sms_sender import send_sms, generate_verification_code
from utils.util_gsheet_editer import is_registered_user

WEBAPP_NAME = "BASECAMP Agent"

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
