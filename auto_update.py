import pandas as pd
import time
import yfinance as yf
from vnstock import listing_companies, price_board
from google_sheet_api import update_dataframe_to_sheet

def get_data_vnstock():
    """Ưu tiên 1: Lấy dữ liệu qua vnstock (Nhanh, real-time, có nhóm ngành)"""
    try:
        print("1. Đang thử lấy dữ liệu qua thư viện vnstock...")
        df_listing = listing_companies()
        df_hose = df_listing[df_listing['comGroupCode'] == 'HOSE'].copy() if 'comGroupCode' in df_listing.columns else df_listing
        hose_tickers = df_hose['ticker'].tolist()
        
        sectors = {}
        if 'sector' in df_listing.columns:
            sectors = df_listing[['ticker', 'sector']].set_index('ticker').to_dict()['sector']

        df_price_list = []
        for i in range(0, len(hose_tickers), 50):
            chunk = hose_tickers[i:i + 50]
            try:
                df_chunk = price_board(chunk)
                if not df_chunk.empty:
                    df_price_list.append(df_chunk)
            except Exception:
                pass 
            time.sleep(0.3)
            
        if not df_price_list:
            return pd.DataFrame() # Trả về rỗng để kích hoạt fallback yfinance

        df_price = pd.concat(df_price_list, ignore_index=True)
        df_res = pd.DataFrame()
        
        col_ma = 'Mã CP' if 'Mã CP' in df_price.columns else 'ticker'
        col_gia = 'Giá Khớp Lệnh' if 'Giá Khớp Lệnh' in df_price.columns else 'Giá'
        col_kl = 'KL Khớp Lệnh' if 'KL Khớp Lệnh' in df_price.columns else 'KL'
        
        df_res['Mã CK'] = df_price[col_ma]
        df_res['Nhóm Ngành'] = df_res['Mã CK'].map(sectors).fillna('Khác')
        df_res['Giá'] = df_price[col_gia] if col_gia in df_price.columns else 0
        df_res['+/-'] = df_price['+/-'] if '+/-' in df_price.columns else 0
        df_res['%'] = df_price['%'] if '%' in df_price.columns else 0
        
        df_res['Tổng KL'] = (df_price[col_kl] * 10) if col_kl in df_price.columns else 0
        df_res['Tổng KL'] = pd.to_numeric(df_res['Tổng KL'], errors='coerce').fillna(0)

        df_res = df_res.sort_values(by='Tổng KL', ascending=False).head(100).reset_index(drop=True)
        return df_res
    except Exception as e:
        print(f"❌ vnstock gặp sự cố: {e}")
        return pd.DataFrame()

def get_data_yfinance():
    """Ưu tiên 2: Lấy dữ liệu qua Yahoo Finance (Chống chặn IP, độ trễ 15p)"""
    try:
        print("2. Đang tự động chuyển sang Yahoo Finance để lấy dữ liệu dự phòng...")
        tickers = [
            "SSI", "VND", "HCM", "VCI", "HPG", "HSG", "NKG", "VHM", "VIC", "VRE",
            "VCB", "CTG", "BID", "TCB", "MBB", "VPB", "STB", "ACB", "TPB", "HDB",
            "FPT", "MWG", "PNJ", "MSN", "VNM", "SAB", "GAS", "PLX", "POW", "GVR",
            "NVL", "PDR", "DIG", "DXG", "KBC", "VGC", "IDC", "KDH", "NLG", "HDG",
            "DGC", "DPM", "DCM", "CSV", "VHC", "ANV", "IDI", "PC1", "REE", "GEG"
        ]
        tickers_hm = [f"{t}.HM" for t in tickers]
        data = yf.download(tickers_hm, period="5d", threads=True, progress=False)
        
        records = []
        for t_base in tickers:
            t_hm = f"{t_base}.HM"
            try:
                closes = data['Close'][t_hm].dropna()
                volumes = data['Volume'][t_hm].dropna()
                if len(closes) < 2: 
                    continue
                    
                ref_price = closes.iloc[-2]
                current_price = closes.iloc[-1]
                volume = volumes.iloc[-1]
                
                change = current_price - ref_price
                pct_change = (change / ref_price) * 100 if ref_price > 0 else 0
                
                records.append({
                    'Mã CK': t_base,
                    'Nhóm Ngành': 'Thị trường VN',
                    'Giá': round(current_price / 1000, 2),
                    '+/-': round(change / 1000, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                })
            except Exception:
                continue
                
        df_res = pd.DataFrame(records)
        if not df_res.empty:
            df_res = df_res.sort_values(by='Tổng KL', ascending=False).reset_index(drop=True)
        return df_res
    except Exception as e:
        print(f"❌ yfinance cũng gặp sự cố: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE ---")
    
    # KỊCH BẢN KẾT HỢP (FALLBACK)
    df_100 = get_data_vnstock()
    
    # Nếu vnstock trả về DataFrame rỗng (do bị chặn hoặc lỗi)
    if df_100.empty:
        print("⚠️ Không lấy được dữ liệu từ vnstock. Kích hoạt yfinance...")
        df_100 = get_data_yfinance()
    else:
        print("✅ Lấy dữ liệu qua vnstock thành công!")
    
    # Đẩy lên Google Sheet
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"Đang đồng bộ {len(df_100)} mã lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Cả vnstock và yfinance đều thất bại. Hủy tiến trình tải lên Sheets.")
