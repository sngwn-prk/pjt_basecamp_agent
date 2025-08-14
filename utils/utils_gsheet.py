import streamlit as st
from streamlit_gsheets import GSheetsConnection
import gspread
from google.oauth2.service_account import Credentials

def format_phone_number(phone):
    try:
        if isinstance(phone, float):
            phone = int(phone)
        
        phone_str = str(phone).replace('.0', '')
        
        if len(phone_str) == 10 and phone_str.isdigit():
            return f"0{phone_str}"
        else:
            return phone_str
    except:
        return str(phone)

def read_sheet_by_df(sheet_name):
    """구글 시트의 데이터를 읽어옵니다."""
    conn = st.connection(sheet_name, type=GSheetsConnection, ttl=0)
    df = conn.read(worksheet=sheet_name, ttl=0)
    if 'phn_no' in df.columns:
        df['phn_no'] = df['phn_no'].apply(format_phone_number)
    if 'author' in df.columns:
        df['author'] = df['author'].apply(format_phone_number)
    return df

def is_registered_user(phone_number, access_type):
    """등록된 사용자인지 확인 - 구글 스프레드시트에서 권한활성여부가 '활성'인 사용자만 확인"""
    try:
        clean_phone = phone_number.replace('-', '').replace(' ', '')

        df = read_sheet_by_df("tbl_mbr_req_incr")        
        df['phn_no'] = df['phn_no'].apply(format_phone_number)

        if access_type == 'admin':
            cond_access = df['access_type']=='관리자'
        else:
            cond_access = df['access_type']=='일반(학생)'

        active_phones = ['0'+str(int(x)) for x in df[(df['status']=='활성') & (cond_access)]['phn_no'].unique().tolist()]
        waiting_phones = ['0'+str(int(x)) for x in df[(df['status']=='대기') & (cond_access)]['phn_no'].unique().tolist()]
        inactive_phones = ['0'+str(int(x)) for x in df[(df['status']=='비활성') & (cond_access)]['phn_no'].unique().tolist()]

        if clean_phone in active_phones:
            return 'active'
        elif clean_phone in waiting_phones:
            return 'waiting'
        elif clean_phone in inactive_phones:
            return 'inactive'
        else:
            return 'not_found'
    except Exception as e:
        return 'not_found'

def get_worksheet(sheet_name):
    connection_info = st.secrets["connections"][sheet_name]
    service_account_info = {
        "type": connection_info["type"],
        "project_id": connection_info["project_id"],
        "private_key_id": connection_info["private_key_id"],
        "private_key": connection_info["private_key"],
        "client_email": connection_info["client_email"],
        "client_id": connection_info["client_id"],
        "auth_uri": connection_info["auth_uri"],
        "token_uri": connection_info["token_uri"],
        "auth_provider_x509_cert_url": connection_info["auth_provider_x509_cert_url"],
        "client_x509_cert_url": connection_info["client_x509_cert_url"]
    }
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        service_account_info, 
        scopes=scope
    )
    gc = gspread.authorize(credentials)

    spreadsheet_url = connection_info["spreadsheet"]
    spreadsheet = gc.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet

def update_sheet_add_row(sheet_name, new_row:list):
    """구글 시트에 새로운 행을 추가합니다."""
    try:
        worksheet = get_worksheet(sheet_name)
        worksheet.append_row(new_row)
        return True
    except Exception as e:
        st.error(f"❌ 행 추가 중 오류: {e}")
        return False

def update_sheet_specific_rows(sheet_name, original_df, updated_df):
    """구글 시트의 변경된 행만 업데이트합니다."""
    try:
        worksheet = get_worksheet(sheet_name)
        
        # 변경된 행 찾기
        changed_rows = []
        
        # 원본 데이터프레임의 인덱스를 req_id로 설정
        original_df_indexed = original_df.set_index('req_id')
        
        for _, updated_row in updated_df.iterrows():
            req_id = updated_row.get('req_id')
            if req_id is not None and req_id in original_df_indexed.index:
                original_row = original_df_indexed.loc[req_id]
                
                # 변경사항이 있는지 확인
                for col in updated_df.columns:
                    if col in original_df.columns and col != 'req_id':
                        if str(updated_row[col]) != str(original_row[col]):
                            changed_rows.append({
                                'req_id': req_id,
                                'column': col,
                                'old_value': original_row[col],
                                'new_value': updated_row[col]
                            })
        
        # 변경된 행들만 업데이트
        updated_count = 0
        for change in changed_rows:
            try:
                # req_id로 행 번호 찾기
                all_data = worksheet.get_all_values()
                headers = all_data[0]
                
                # req_id 컬럼 인덱스 찾기
                req_id_col_idx = None
                for i, header in enumerate(headers):
                    if header == 'req_id':
                        req_id_col_idx = i
                        break
                
                if req_id_col_idx is not None:
                    # req_id가 일치하는 행 찾기
                    row_idx = None
                    for i, row in enumerate(all_data[1:], start=2):  # 2부터 시작 (헤더 제외)
                        if len(row) > req_id_col_idx and str(row[req_id_col_idx]) == str(change['req_id']):
                            row_idx = i
                            break
                    
                    if row_idx is not None:
                        # 변경할 컬럼의 인덱스 찾기
                        col_idx = None
                        for i, header in enumerate(headers):
                            if header == change['column']:
                                col_idx = i
                                break
                        
                        if col_idx is not None:
                            # 셀 업데이트 (예: A2, B3 등)
                            cell_address = f"{chr(65 + col_idx)}{row_idx}"  # A=65, B=66, ...
                            worksheet.update(cell_address, str(change['new_value']))
                            updated_count += 1
                            
            except Exception as e:
                st.error(f"❌ 행 업데이트 중 오류 (req_id: {change['req_id']}): {e}")
                continue
        
        return True, updated_count
        
    except ImportError:
        st.error("❌ gspread 라이브러리가 설치되지 않았습니다.")
        st.info("pip install gspread google-auth를 실행해주세요.")
        return False, 0
    except Exception as e:
        st.error(f"❌ 시트 업데이트 중 오류: {e}")
        return False, 0
