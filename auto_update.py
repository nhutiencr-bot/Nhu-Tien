import pandas as pd
import yfinance as yf
from google_sheet_api import update_dataframe_to_sheet

def get_live_market_data_yfinance():
    """Lấy dữ liệu chứng khoán Việt Nam qua Yahoo Finance để tránh bị chặn IP trên Cloud"""
    try:
        # 1. Danh sách các mã phổ biến (Bạn có thể thêm bớt tùy ý để đủ 100 mã)
        # Yahoo Finance quy định mã sàn HOSE phải có đuôi ".HM"
        tickers = [
            "SSI", "VND", "HCM", "VCI", "HPG", "HSG", "NKG", "VHM", "VIC", "VRE",
            "VCB", "CTG", "BID", "TCB", "MBB", "VPB", "STB", "ACB", "TPB", "HDB",
            "FPT", "MWG", "PNJ", "MSN", "VNM", "SAB", "GAS", "PLX", "POW", "GVR",
            "NVL", "PDR", "DIG", "DXG", "KBC", "VGC", "IDC", "KDH", "NLG", "HDG",
            "DGC", "DPM", "DCM", "CSV", "VHC", "ANV", "IDI", "PC1", "REE", "GEG"
        ]
        
        tickers_hm = [f"{t}.HM" for t in tickers]
        print(f"Đang tải dữ liệu {len(tickers)} mã từ Yahoo Finance...")
        
        # 2. Tải dữ liệu 5 phiên gần nhất (để lấy giá đóng cửa phiên trước làm tham chiếu)
        # yfinance sẽ tải đồng loạt nên tốc độ rất nhanh
        data = yf.download(tickers_hm, period="5d", threads=True, progress=False)
        
        records = []
        
        for t_base in tickers:
            t_hm = f"{t_base}.HM"
            try:
                # Trích xuất dữ liệu của từng mã
                closes = data['Close'][t_hm].dropna()
                volumes = data['Volume'][t_hm].dropna()
                
                if len(closes) < 2: # Bỏ qua nếu dữ liệu không đủ (VD: mã mới lên sàn)
                    continue
                    
                # Tính toán giá tham chiếu và giá hiện tại
                ref_price = closes.iloc[-2]     # Giá đóng cửa phiên trước đó
                current_price = closes.iloc[-1] # Giá hiện tại (hoặc đóng cửa phiên nay)
                volume = volumes.iloc[-1]       # Khối lượng giao dịch hiện tại
                
                change = current_price - ref_price
                pct_change = (change / ref_price) * 100 if ref_price > 0 else 0
                
                records.append({
                    'Mã CK': t_base,
                    'Nhóm Ngành': 'Thị trường VN', # Yahoo ko phân ngành tiếng Việt, gán mặc định
                    'Giá': round(current_price / 1000, 2), # Chia 1000 để giống bảng giá VN (VD: 34500 -> 34.5)
                    '+/-': round(change / 1000, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                })
            except Exception:
                continue
                
        # 3. Tạo DataFrame và sắp xếp theo Khối Lượng
        df_res = pd.DataFrame(records)
        
        if not df_res.empty:
            df_res = df_res.sort_values(by='Tổng KL', ascending=False).reset_index(drop=True)
            
        return df_res

    except Exception as e:
        print(f"❌ Lỗi tổng thể khi lấy dữ liệu bằng yfinance: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("--- BẮT ĐẦU CHẠY AUTO UPDATE QUA YAHOO FINANCE ---")
    
    df_100 = get_live_market_data_yfinance()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"✅ Đã xử lý thành công {len(df_100)} mã chứng khoán.")
        print(f"Đang đồng bộ lên Google Sheet: {TEN_FILE_SHEET} ...")
        
        # Đẩy dữ liệu qua module google_sheet_api.py của bạn
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã hoàn tất đẩy dữ liệu lên Google Sheets!")
        else:
            print(f"❌ Lỗi cấu hình Google Sheets: {message}")
    else:
        print("❌ Dữ liệu trống. Hủy tiến trình tải lên Sheets.")
