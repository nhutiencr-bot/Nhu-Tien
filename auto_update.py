import pandas as pd
from vnstock import listing_companies, price_board
from google_sheet_api import update_dataframe_to_sheet

def get_live_market_data():
    """Lấy dữ liệu Top 100 (rổ VN100) trực tiếp bằng thư viện vnstock"""
    try:
        print("Đang tải danh sách công ty và nhóm ngành từ vnstock...")
        # 1. Lấy danh sách công ty để phân loại nhóm ngành
        df_listing = listing_companies()
        sectors = df_listing[['ticker', 'sector']].set_index('ticker').to_dict()['sector']

        print("Đang tải bảng giá rổ VN100...")
        # 2. Lấy trực tiếp bảng giá của 100 mã lớn nhất thị trường
        # vnstock sẽ tự động xử lý request và headers để không bị chặn
        df_price = price_board('VN100')

        if df_price.empty:
            print("⚠️ Cảnh báo: Bảng giá vnstock trả về trống.")
            return pd.DataFrame()

        # 3. Chuẩn hóa lại tên cột cho khớp với định dạng Google Sheet cũ của bạn
        df_res = pd.DataFrame()
        df_res['Mã CK'] = df_price['Mã CP']
        df_res['Nhóm Ngành'] = df_res['Mã CK'].map(sectors).fillna('Khác')
        
        # vnstock thường trả về tên cột tiếng Việt, ta map lại cho chuẩn:
        col_gia = 'Giá Khớp Lệnh' if 'Giá Khớp Lệnh' in df_price.columns else 'Giá'
        col_kl = 'KL Khớp Lệnh' if 'KL Khớp Lệnh' in df_price.columns else 'KL'
        
        df_res['Giá'] = df_price[col_gia] if col_gia in df_price.columns else 0
        df_res['+/-'] = df_price['+/-'] if '+/-' in df_price.columns else 0
        df_res['%'] = df_price['%'] if '%' in df_price.columns else 0
        
        # Trên bảng giá chuẩn, Khối lượng thường được chia 10, nên ta nhân 10 lại để ra số thực
        df_res['Tổng KL'] = (df_price[col_kl] * 10) if col_kl in df_price.columns else 0 

        # 4. Sắp xếp danh sách theo Tổng Khối Lượng từ cao xuống thấp
        df_res = df_res.sort_values(by='Tổng KL', ascending=False).reset_index(drop=True)
        
        return df_res

    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu bằng vnstock: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE ---")
    
    df_100 = get_live_market_data()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"✅ Đã lấy thành công {len(df_100)} mã chứng khoán.")
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        # Đẩy dữ liệu qua module google_sheet_api.py
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Dữ liệu trống. Hủy tiến trình tải lên Sheets.")
