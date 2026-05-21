import pandas as pd
import requests
import time
from vnstock import listing_companies
from google_sheet_api import update_dataframe_to_sheet

def get_sectors():
    try:
        df = listing_companies()
        return df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

def get_live_market_data():
    try:
        url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVol~DESC&q=floor:HOSE&size=100&_t={int(time.time())}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            sectors = get_sectors()
            res = []
            for i in r.json()['data']:
                tk = i.get('code')
                res.append({
                    'Mã CK': tk, 
                    'Nhóm Ngành': sectors.get(tk, 'Khác'),
                    'Giá': i.get('matchPrice', 0), 
                    '+/-': i.get('priceChange', 0), 
                    '%': i.get('changePc', 0), 
                    'Tổng KL': i.get('accumulatedVol', 0)
                })
            return pd.DataFrame(res)
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu: {e}")
    return pd.DataFrame()

if __name__ == "__main__":
    print("Bắt đầu lấy dữ liệu Top 100...")
    df_100 = get_live_market_data()
    
    if not df_100.empty:
        TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien"
        print(f"Đang đẩy dữ liệu lên file: {TEN_FILE_SHEET}")
        
        # Gọi hàm đẩy dữ liệu từ google_sheet_api.py
        success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
        
        if success:
            print("✅ Đã cập nhật dữ liệu tự động thành công!")
        else:
            print(f"❌ Lỗi: {message}")
    else:
        print("⚠️ Không lấy được dữ liệu thị trường.")
