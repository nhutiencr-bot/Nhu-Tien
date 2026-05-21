import pandas as pd
import yfinance as yf
from vnstock import listing_companies
from google_sheet_api import update_dataframe_to_sheet

def get_market_data_safe():
    try:
        print("1. Đang tải danh sách mã từ vnstock...")
        df_listing = listing_companies()
        df_hose = df_listing[df_listing['comGroupCode'] == 'HOSE'].copy() if 'comGroupCode' in df_listing.columns else df_listing
        hose_tickers = df_hose['ticker'].tolist()
        
        sector_col = 'sector' if 'sector' in df_listing.columns else ('industry' if 'industry' in df_listing.columns else 'groupName')
        sectors = {}
        if sector_col in df_listing.columns:
            sectors = df_listing[['ticker', sector_col]].set_index('ticker').to_dict()[sector_col]

        print(f"2. Tải bảng giá {len(hose_tickers)} mã từ Yahoo Finance (An toàn 100%)...")
        tickers_hm = [f"{t}.HM" for t in hose_tickers]
        data = yf.download(tickers_hm, period="5d", threads=True, progress=False)
        
        records = []
        for t_base in hose_tickers:
            t_hm = f"{t_base}.HM"
            try:
                closes = data['Close'][t_hm].dropna()
                volumes = data['Volume'][t_hm].dropna()
                if len(closes) < 2: continue
                    
                ref_price = float(closes.iloc[-2])
                current_price = float(closes.iloc[-1])
                volume = float(volumes.iloc[-1])
                change = current_price - ref_price
                
                records.append({
                    'Mã CK': t_base,
                    'Nhóm Ngành': sectors.get(t_base, 'Khác'),
                    'Giá': round(current_price / 1000, 2),
                    '+/-': round(change / 1000, 2),
                    '%': round((change / ref_price) * 100 if ref_price > 0 else 0, 2),
                    'Tổng KL': int(volume)
                })
            except Exception:
                continue
                
        df_res = pd.DataFrame(records)
        if not df_res.empty:
            df_res = df_res.sort_values(by='Tổng KL', ascending=False).head(100).reset_index(drop=True)
        return df_res
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- CHẠY FILE MỚI: VNSTOCK + YFINANCE ---")
    df_100 = get_market_data_safe()
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        if success: print("✅ Xong!")
        else: print(f"❌ Lỗi: {message}")
