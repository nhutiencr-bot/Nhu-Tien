import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st  # 🌟 Vẫn giữ nguyên để phục vụ UI

CREDENTIALS_FILE = 'credentials.json'

def get_sheet_client():
    """Hàm khởi tạo kết nối với Google Sheets API tương thích cho cả Streamlit và GitHub Actions"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # 1. ƯU TIÊN 1: Chạy trên GitHub Actions hoặc máy tính cá nhân (đã có file credentials.json)
    if os.path.exists(CREDENTIALS_FILE):
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        
    # 2. ƯU TIÊN 2: Chạy trên Web Streamlit Cloud (không có file vật lý, phải dùng st.secrets)
    elif "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
    else:
        raise Exception("Không tìm thấy thông tin xác thực Google API ở bất kỳ đâu!")
        
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
