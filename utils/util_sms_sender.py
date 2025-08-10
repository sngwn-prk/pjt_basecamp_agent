import hashlib
import hmac
import base64
import time
import random
import string
import requests
# import os

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

def send_sms(phone_number, cert_code):
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
        "content": "[BASECAMP Agent] 인증번호",
        "messages":[
            {
                "to": phone_number,
                "content": f"[BASECAMP Agent]\n인증번호: {cert_code}\n타인 유출로 인한 피해 주의"
            }
        ]
    }
    SMS_URL = f'https://sens.apigw.ntruss.com/sms/v2/services/{NCP_SMS_SVC_ID}/messages'
    response = requests.post(SMS_URL, headers=headers, json=body)
    return response.json()

def generate_verification_code():
    """6자리 인증번호 생성"""
    return ''.join(random.choices(string.digits, k=6))
