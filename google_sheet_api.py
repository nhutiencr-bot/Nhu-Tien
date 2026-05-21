import streamlit as st
def get_sheet_client():
    """Hàm khởi tạo kết nối với Google Sheets API"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Nếu chạy trên Streamlit Cloud, lấy trực tiếp từ Secrets
    if "gcp_service_account" in st.secrets:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            dict(st.secrets["gcp_service_account"]), scope
        )
    # Nếu chạy dưới máy local, đọc từ file credentials.json
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        
    client = gspread.authorize(creds)
    return client
