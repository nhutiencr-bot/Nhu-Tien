import pandas as pd
import yfinance as yf
from vnstock import listing_companies
from google_sheet_api import update_dataframe_to_sheet

def get_market_data_safe():
    """Dùng vnstock lấy danh sách ngành + yfinance lấy giá để né chặn IP"""
    try:
        print("1. Đang tải danh sách mã và nhóm ngành từ vnstock...")
        # 1. Chỉ dùng vnstock để lấy danh sách công ty (Không dùng để lấy giá)
        df_listing = listing_companies()
        
        # Lọc các mã sàn HOSE
        df_hose = df_listing[df_listing['comGroupCode'] == 'HOSE'].copy() if 'comGroupCode' in df_listing.columns else df_listing
        hose_tickers = df_hose['ticker'].tolist()
        
        # Mapping Nhóm ngành
        sector_col = 'sector' if 'sector' in df_listing.columns else ('industry' if 'industry' in df_listing.columns else 'groupName')
        sectors = {}
        if sector_col in df_listing.columns:
            sectors = df_listing[['ticker', sector_col]].set_index('ticker').to_dict()[sector_col]

        print(f"2. Lấy dữ liệu giao dịch cho {len(hose_tickers)} mã từ Yahoo Finance (Không qua CTCK)...")
        # 2. Dùng yfinance để lấy giá (Bypass hoàn toàn tường lửa của VNDirect)
        tickers_hm = [f"{t}.HM" for t in hose_tickers]
        
        # Tải dữ liệu hàng loạt từ Yahoo Finance
        data = yf.download(tickers_hm, period="5d", threads=True, progress=False)
        
        records = []
        for t_base in hose_tickers:
            t_hm = f"{t_base}.HM"
            try:
                # Trích xuất giá đóng cửa và khối lượng
                closes = data['Close'][t_hm].dropna()
                volumes = data['Volume'][t_hm].dropna()
                
                if len(closes) < 2: 
                    continue
                    
                ref_price = float(closes.iloc[-2])     # Giá tham chiếu (hôm qua)
                current_price = float(closes.iloc[-1]) # Giá hiện tại
                volume = float(volumes.iloc[-1])       # Khối lượng
                
                change = current_price - ref_price
                pct_change = (change / ref_price) * 100 if ref_price > 0 else 0
                
                records.append({
                    'Mã CK': t_base,
                    'Nhóm Ngành': sectors.get(t_base, 'Khác'), # Ghép nhóm ngành từ vnstock
                    'Giá': round(current_price / 1000, 2),
                    '+/-': round(change / 1000, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                })
            except Exception:
                continue
                
        # 3. Tạo bảng, sắp xếp và lấy TOP 100 khối lượng
        df_res = pd.DataFrame(records)
        
        if not df_res.empty:
            df_res = df_res.sort_values(by='Tổng KL', ascending=False).head(100).reset_index(drop=True)
            
        return df_res

    except Exception as e:
        print(f"❌ Lỗi hệ thống: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE (VNSTOCK + YFINANCE) ---")
    
    df_100 = get_market_data_safe()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"✅ Đã xử lý thành công {len(df_100)} mã chứng khoán (Top 100).")
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Dữ liệu trống. Hủy tiến trình tải lên Sheets.")
