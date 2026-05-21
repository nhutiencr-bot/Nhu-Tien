import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st  # 🌟 BẮT BUỘC PHẢI CÓ DÒNG NÀY

CREDENTIALS_FILE = 'credentials.json'

def get_sheet_client():
    """Hàm khởi tạo kết nối với Google Sheets API"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Nếu chạy trên Streamlit Cloud và đã cấu hình Secrets TOML thành công
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
    # Nếu chạy dưới máy cá nhân (local)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        
    client = gspread.authorize(creds)
    return client

def update_dataframe_to_sheet(sheet_name, df, worksheet_index=0):
    """Hàm đẩy toàn bộ dữ liệu từ DataFrame lên Google Sheet"""
    try:
        client = get_sheet_client()
        sheet = client.open(sheet_name).get_worksheet(worksheet_index)
        sheet.clear()
        
        data_to_upload = [df.columns.values.tolist()] + df.values.tolist()
        sheet.update('A1', data_to_upload)
        return True, "Thành công"
    except Exception as e:
        return False, str(e)
