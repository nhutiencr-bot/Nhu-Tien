import pandas as pd
import yfinance as yf
from vnstock3 import Vnstock
from google_sheet_api import update_dataframe_to_sheet

def get_market_data_safe():
    """Dùng vnstock3 lấy danh sách ngành (Server TCBS) + yfinance lấy giá để né chặn IP"""
    try:
        print("1. Đang tải danh sách mã và nhóm ngành từ vnstock3 (Nguồn TCBS)...")
        # Khởi tạo vnstock3 với nguồn mặc định (thường là TCBS, ổn định hơn)
        stock = Vnstock().stock(symbol='SSI', source='TCBS')
        
        # Lấy danh sách toàn bộ mã chứng khoán
        df_listing = stock.listing.all_symbols()
        
        # Lọc các mã sàn HOSE
        df_hose = df_listing[df_listing['exchange'] == 'HOSE'].copy() if 'exchange' in df_listing.columns else df_listing
        hose_tickers = df_hose['ticker'].tolist()
        
        # Mapping Nhóm ngành
        sector_col = 'icb_name3' if 'icb_name3' in df_listing.columns else ('industry' if 'industry' in df_listing.columns else 'group_name')
        sectors = {}
        if sector_col in df_listing.columns:
            sectors = df_listing[['ticker', sector_col]].set_index('ticker').to_dict()[sector_col]

        print(f"2. Đang tải bảng giá {len(hose_tickers)} mã từ Yahoo Finance (Hoàn toàn độc lập với CTCK Việt Nam)...")
        tickers_hm = [f"{t}.HM" for t in hose_tickers]
        
        data = yf.download(tickers_hm, period="5d", threads=True, progress=False)
        
        records = []
        for t_base in hose_tickers:
            t_hm = f"{t_base}.HM"
            try:
                closes = data['Close'][t_hm].dropna()
                volumes = data['Volume'][t_hm].dropna()
                
                if len(closes) < 2: 
                    continue
                    
                ref_price = float(closes.iloc[-2])
                current_price = float(closes.iloc[-1])
                volume = float(volumes.iloc[-1])
                
                change = current_price - ref_price
                pct_change = (change / ref_price) * 100 if ref_price > 0 else 0
                
                records.append({
                    'Mã CK': t_base,
                    'Nhóm Ngành': sectors.get(t_base, 'Khác'),
                    'Giá': round(current_price / 1000, 2),
                    '+/-': round(change / 1000, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                })
            except Exception:
                continue
                
        df_res = pd.DataFrame(records)
        
        if not df_res.empty:
            df_res = df_res.sort_values(by='Tổng KL', ascending=False).head(100).reset_index(drop=True)
            
        return df_res

    except Exception as e:
        print(f"❌ Lỗi hệ thống: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE (VNSTOCK3 + YFINANCE) ---")
    
    df_100 = get_market_data_safe()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien" # Thay tên sheet của bạn nếu cần
        print(f"✅ Đã xử lý thành công {len(df_100)} mã chứng khoán.")
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Dữ liệu trống. Hủy tiến trình tải lên Sheets.")
