import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# 2. THIẾT LẬP THỜI GIAN VÀ KHUNG GIỜ GIAO DỊCH
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=5)).strftime('%Y-%m-%d')

is_weekday = current_time.weekday() < 5
current_hour = current_time.hour
current_minute = current_time.minute
is_trading_hours = is_weekday and ((9 <= current_hour < 15) or (current_hour == 15 and current_minute <= 30))

if is_trading_hours:
    st.sidebar.success(f"🟢 ĐANG GIAO DỊCH\n\nCập nhật: {current_time.strftime('%H:%M:%S')}")
else:
    st.sidebar.warning(f"🔴 ĐÃ ĐÓNG CỬA\n\nChốt phiên: {end_date}")

# 3. CÁC HÀM LẤY DỮ LIỆU
@st.cache_data(ttl=86400)
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except:
        return {}

@st.cache_data(ttl=300)
def get_dynamic_top_100():
    sector_dict = get_company_sectors()
    tickers = list(sector_dict.keys())
    
    def fetch_ticker(ticker):
        try:
            df = stock_historical_data(
                symbol=ticker, 
                start_date=start_date_stock, 
                end_date=end_date, 
                resolution='1D', 
                type='stock'
            )
            if len(df) >= 2:
                close_today = df.iloc[-1]['close']
                close_yest = df.iloc[-2]['close']
                change = close_today - close_yest
                pct_change = (change / close_yest) * 100
                return {
                    'Mã CK': ticker, 
                    'Nhóm Ngành': sector_dict.get(ticker, 'Khác'), 
                    'Giá': close_today, 
                    '+/-': round(change, 2), 
                    '%': round(pct_change, 2), 
                    'Tổng KL': int(df.iloc[-1]['volume'])
                }
        except:
            return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0: results.append(res)
                
    df_market = pd.DataFrame(results)
    if not df_market.empty: 
        return df_market.sort_values(by='Tổng KL', ascending=False).head(100)
    return df_market

# HÀM LẤY ĐÓNG GÓP ĐIỂM SỐ (DÙNG API TCBS - MƯỢT MÀ KHÔNG BỊ CHẶN)
@st.cache_data(ttl=60)
def get_exact_contribution(df_top):
    # Lớp 1: Gọi API của TCBS
    try:
        url = "https://apip
