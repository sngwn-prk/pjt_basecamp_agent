# import os

import hashlib
import hmac
import base64
import time
import random
import string
import requests

import streamlit as st
from utils.utils_gsheet import update_sheet_add_row

# from dotenv import load_dotenv
# load_dotenv()
# NCP_ACCESS_KEY = os.getenv("NCP_ACCESS_KEY")
# NCP_SECRET_KEY = os.getenv("NCP_SECRET_KEY")
# NCP_SMS_SVC_ID = os.getenv("NCP_SMS_SVC_ID")
# NCP_SMS_SENDER = os.getenv("NCP_SMS_SENDER")

NCP_ACCESS_KEY = st.secrets["NCP_ACCESS_KEY"]
NCP_SECRET_KEY = st.secrets["NCP_SECRET_KEY"]
NCP_SMS_SVC_ID = st.secrets["NCP_SMS_SVC_ID"]
NCP_SMS_SENDER = st.secrets["NCP_SMS_SENDER"]

def make_signature(timestamp):
    secret_key = bytes(NCP_SECRET_KEY, "UTF-8")
    uri = f"/sms/v2/services/{NCP_SMS_SVC_ID}/messages"
    message = f"POST {uri}\n{timestamp}\n{NCP_ACCESS_KEY}"
    message = bytes(message, "UTF-8")
    return base64.b64encode(hmac.new(secret_key, message, digestmod=hashlib.sha256).digest()) 

def send_sms(date_partition, create_dt, phone_number, sms_type, sms_body):
    timestamp = str(int(time.time() * 1000))
    signature = make_signature(timestamp)
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'x-ncp-apigw-timestamp': timestamp,
        'x-ncp-iam-access-key': NCP_ACCESS_KEY,
        'x-ncp-apigw-signature-v2': signature
    }
    body = {
        "type":'sms',
        "contentType":"COMM",
        "countryCode":'82',
        "from":NCP_SMS_SENDER,
        "content": sms_type,
        "messages":[
            {
                "to": phone_number,
                "content": sms_body
            }
        ]
    }
    SMS_URL = f'https://sens.apigw.ntruss.com/sms/v2/services/{NCP_SMS_SVC_ID}/messages'
    response = requests.post(SMS_URL, headers=headers, json=body)
    result = response.json()
    if result.get('statusCode') == '202':
        try:
            update_sheet_add_row("tbl_sms_log_incr", [date_partition, create_dt, phone_number, sms_type])
        except Exception as e:
            st.warning(f"⚠️ 문자 발송 내역 기록 중 오류 발생: {e}")

    return result

def generate_verification_code():
    """6자리 인증번호 생성"""
    return ''.join(random.choices(string.digits, k=6))
