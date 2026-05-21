import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Đường dẫn tới file JSON bạn tải về ở Bước 3
CREDENTIALS_FILE = 'credentials.json'

def get_sheet_client():
    """Hàm khởi tạo kết nối với Google Sheets API"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    # Xác thực bằng file JSON
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def update_dataframe_to_sheet(sheet_name, df, worksheet_index=0):
    """
    Hàm đẩy toàn bộ dữ liệu từ DataFrame lên Google Sheet
    - sheet_name: Tên của file Google Sheet (ví dụ: 'Data_Chung_Khoan')
    - df: Bảng dữ liệu Pandas chứa thông tin mã chứng khoán
    """
    try:
        client = get_sheet_client()
        # Mở file Sheet theo tên và chọn trang tính (mặc định là trang đầu tiên)
        sheet = client.open(sheet_name).get_worksheet(worksheet_index)
        
        # Xóa toàn bộ dữ liệu cũ trên trang tính
        sheet.clear()
        
        # Chuyển đổi DataFrame thành dạng List of Lists (Bao gồm cả dòng Tiêu đề)
        data_to_upload = [df.columns.values.tolist()] + df.values.tolist()
        
        # Đẩy dữ liệu lên bắt đầu từ ô A1
        sheet.update(values=data_to_upload, range_name='A1')
        print(f"✅ Đã cập nhật thành công dữ liệu lên sheet: {sheet_name}")
        
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật lên Google Sheets: {e}")
