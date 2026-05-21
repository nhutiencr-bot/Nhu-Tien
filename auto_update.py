import pandas as pd
import time
from vnstock import listing_companies, price_board
from google_sheet_api import update_dataframe_to_sheet

def get_live_market_data():
    """Lấy dữ liệu Top 100 HOSE có khối lượng giao dịch cao nhất bằng thư viện vnstock"""
    try:
        print("Đang tải danh sách công ty và nhóm ngành từ vnstock...")
        # 1. Lấy danh sách toàn bộ công ty
        df_listing = listing_companies()
        
        # Lọc lấy các mã thuộc sàn HOSE
        df_hose = df_listing[df_listing['comGroupCode'] == 'HOSE'].copy() if 'comGroupCode' in df_listing.columns else df_listing
        hose_tickers = df_hose['ticker'].tolist()
        
        # Xây dựng từ điển mapping Nhóm ngành linh hoạt (tùy phiên bản vnstock)
        sector_col = 'sector' if 'sector' in df_listing.columns else ('industry' if 'industry' in df_listing.columns else 'groupName')
        sectors = {}
        if sector_col in df_listing.columns:
            sectors = df_listing[['ticker', sector_col]].set_index('ticker').to_dict()[sector_col]

        print(f"Đã tìm thấy {len(hose_tickers)} mã trên HOSE. Đang tải bảng giá (có thể mất vài giây)...")
        
        # 2. Lấy dữ liệu bảng giá theo từng cụm (chunk) để tránh lỗi URL quá dài từ API
        chunk_size = 50
        df_price_list = []
        
        for i in range(0, len(hose_tickers), chunk_size):
            chunk = hose_tickers[i:i + chunk_size]
            try:
                df_chunk = price_board(chunk)
                if not df_chunk.empty:
                    df_price_list.append(df_chunk)
            except Exception as e:
                print(f"Lỗi khi lấy dữ liệu cụm {chunk[0]}... : {e}")
            time.sleep(0.3) # Nghỉ một chút để tránh bị server chặn (Rate limit)
            
        if not df_price_list:
            print("⚠️ Cảnh báo: Không lấy được dữ liệu bảng giá nào.")
            return pd.DataFrame()

        # Gộp tất cả các cụm lại thành 1 bảng duy nhất
        df_price = pd.concat(df_price_list, ignore_index=True)

        # 3. Chuẩn hóa tên cột
        df_res = pd.DataFrame()
        
        # Tìm đúng tên cột chứa mã cổ phiếu
        col_ma = 'Mã CP' if 'Mã CP' in df_price.columns else ('Mã' if 'Mã' in df_price.columns else 'ticker')
        if col_ma not in df_price.columns:
            print("⚠️ Không tìm thấy cột Mã CK trong dữ liệu trả về.")
            return pd.DataFrame()
            
        df_res['Mã CK'] = df_price[col_ma]
        df_res['Nhóm Ngành'] = df_res['Mã CK'].map(sectors).fillna('Khác')
        
        # Xử lý linh hoạt các tên cột bảng giá
        col_gia = 'Giá Khớp Lệnh' if 'Giá Khớp Lệnh' in df_price.columns else 'Giá'
        col_kl = 'KL Khớp Lệnh' if 'KL Khớp Lệnh' in df_price.columns else ('Khối Lượng' if 'Khối Lượng' in df_price.columns else 'KL')
        
        df_res['Giá'] = df_price[col_gia] if col_gia in df_price.columns else 0
        df_res['+/-'] = df_price['+/-'] if '+/-' in df_price.columns else 0
        df_res['%'] = df_price['%'] if '%' in df_price.columns else 0
        
        # Nhân 10 khối lượng và ép kiểu dữ liệu về số học để đảm bảo có thể sort (tránh dính text)
        df_res['Tổng KL'] = (df_price[col_kl] * 10) if col_kl in df_price.columns else 0
        df_res['Tổng KL'] = pd.to_numeric(df_res['Tổng KL'], errors='coerce').fillna(0)

        # 4. Sắp xếp theo Tổng Khối Lượng từ cao xuống thấp và CẮT LẤY TOP 100
        df_res = df_res.sort_values(by='Tổng KL', ascending=False).head(100).reset_index(drop=True)
        
        return df_res

    except Exception as e:
        print(f"❌ Lỗi tổng thể khi lấy dữ liệu bằng vnstock: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE ---")
    
    df_100 = get_live_market_data()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"✅ Đã lấy thành công {len(df_100)} mã chứng khoán (Top 100 Khối Lượng).")
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        # Đẩy dữ liệu qua module google_sheet_api.py
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Dữ liệu trống. Hủy tiến trình tải lên Sheets.")
