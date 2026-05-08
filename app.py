import streamlit as st
import pandas as pd
# Cập nhật: Thêm hàm ticker_overview để lấy Số lượng cổ phiếu lưu hành
from vnstock import stock_historical_data, listing_companies, ticker_overview
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

# 2. THIẾT LẬP THỜI GIAN VÀ KHUNG GIỜ
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
            df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
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

# HÀM LẤY SỐ LƯỢNG CỔ PHIẾU LƯU HÀNH (Chỉ chạy 1 lần/ngày)
@st.cache_data(ttl=86400)
def get_outstanding_shares(tickers):
    shares_dict = {}
    def fetch_shares(ticker):
        try:
            df = ticker_overview(ticker)
            # Lấy số lượng CP lưu hành (triệu CP)
            return ticker, df['outstandingShare'].iloc[0] 
        except:
            return ticker, 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_shares, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            t, s = future.result()
            if s > 0: shares_dict[t] = s
    return shares_dict

# HÀM LẤY ĐÓNG GÓP ĐIỂM SỐ (CHUẨN VỐN HÓA 100%)
@st.cache_data(ttl=60)
def get_exact_contribution(df_top, vnindex_ref_price):
    # Lớp 1: Gọi API của TCBS (Số chuẩn Sở GDCK)
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'data' in data and len(data['data']) > 0:
                df = pd.DataFrame(data['data'])
                return df[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except:
        pass

    # Lớp 2: Dùng vnstock3 (Số chuẩn Sở GDCK)
    try:
        from vnstock3 import Vnstock
        vn = Vnstock()
        df = vn.market_watch.tickers_contrib_index(index='VNINDEX')
        if not df.empty:
            str_cols = [c for c in df.columns if df[c].dtype == 'object']
            num_cols = [c for c in df.columns if df[c].dtype != 'object']
            if str_cols and num_cols:
                return df[[str_cols[0], num_cols[0]]].rename(columns={str_cols[0]: 'Mã CK', num_cols[0]: 'Điểm'})
    except:
        pass

    # Lớp 3: TỰ TÍNH TOÁN CHUẨN XÁC DỰA TRÊN VỐN HÓA (Dự phòng cực mạnh)
    if not df_top.empty and vnindex_ref_price > 0:
        df_sim = df_top.copy()
        
        # 1. Kéo Khối lượng lưu hành thực tế
        shares = get_outstanding_shares(df_sim['Mã CK'].tolist())
        df_sim['KL_Luu_Hanh'] = df_sim['Mã CK'].map(shares).fillna(0)
        
        # 2. Tính Giá tham chiếu của từng mã (Giá hiện tại - Mức thay đổi)
        df_sim['Gia_Tham_Chieu'] = df_sim['Giá'] - df_sim['+/-']
        
        # 3. Tính Vốn hóa (Market Cap) = Giá tham chiếu x KL Lưu hành
        df_sim['Von_Hoa'] = df_sim['Gia_Tham_Chieu'] * df_sim['KL_Luu_Hanh']
        
        # 4. Giả định Top 100 chiếm khoảng 85% tổng vốn hóa sàn HOSE
        total_market_cap_estimate = df_sim['Von_Hoa'].sum() / 0.85 
        
        # 5. Tính Tỷ trọng vốn hóa (Weight)
        df_sim['Ty_Trong'] = df_sim['Von_Hoa'] / total_market_cap_estimate
        
        # 6. TÍNH ĐIỂM ĐÓNG GÓP: Điểm Index Cũ x Tỷ Trọng x % Thay đổi
        df_sim['Điểm'] = vnindex_ref_price * df_sim['Ty_Trong'] * (df_sim['%'] / 100)
        
        return df_sim[['Mã CK', 'Điểm']]

    return pd.DataFrame()

# MÀU SẮC CHUẨN ĐỂ HIỂN THỊ
COLOR_CEIL = '#cc00ff'
COLOR_GREEN = '#00e676'
COLOR_REF = '#f5b041'
COLOR_RED = '#ff4d4d'
COLOR_DRED = '#b30000'
COLOR_FLOOR = '#00e5ff'

custom_color_scale = [
    [0.0, COLOR_FLOOR], [0.014, COLOR_FLOOR], [0.014, COLOR_DRED], [0.285, COLOR_DRED],
    [0.285, COLOR_RED], [0.499, COLOR_RED], [0.499, COLOR_REF], [0.501, COLOR_REF],
    [0.501, COLOR_GREEN], [0.985, COLOR_GREEN], [0.985, COLOR_CEIL], [1.0, COLOR_CEIL]
]

df_top100 = get_dynamic_top_100()

# 4. GIAO DIỆN 3 TABS
tab1, tab2, tab3 = st.tabs(["📈 VN-INDEX & Tác động", "🗺️ Bản đồ dòng tiền", "📊 Top 100 Active"])

# ==========================================
# TAB 1: VN-INDEX & ĐÓNG GÓP ĐIỂM SỐ
# ==========================================
with tab1:
    @st.cache_data(ttl=60)
    def get_realtime_index():
        return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

    try:
        df_index = get_realtime_index()
        ref_price_index = 1250 # Giá trị dự phòng nếu lỗi
        
        if not df_index.empty:
            df_index['date'] = pd.to_datetime(df_index['time']).dt.date
            unique_dates = df_index['date'].unique()
            
            if len(unique_dates) >= 2:
                df_today = df_index[df_index['date'] == unique_dates[-1]].copy()
                df_yest = df_index[df_index['date'] == unique_dates[-2]].copy()
                
                current_score = df_today.iloc[-1]['close']
                ref_price_index = df_yest.iloc[-1]['close'] # Lấy điểm tham chiếu thực tế
                point_change = current_score - ref_price_index
                pct_change = (point_change / ref_price_index) * 100
                
                st.metric(
                    label=f"VN-INDEX (Lúc: {df_today.iloc[-1]['time']})", 
                    value=f"{current_score:,.2f}", 
                    delta=f"{point_change:+,.2f} điểm ({pct_change:+,.2f}%)"
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🌊 Thanh khoản (Hôm nay vs Hôm qua)")
                    df_today['time_str'] = pd.to_datetime(df_today['time']).dt.strftime('%H:%M')
                    df_yest['time_str'] = pd.to_datetime(df_yest['time']).dt.strftime('%H:%M')
                    df_today['cum_vol'] = df_today['volume'].cumsum()
                    df_yest['cum_vol'] = df_yest['volume'].cumsum()
                    
                    fig_liq = go.Figure()
                    fig_liq.add_trace(go.Scatter(
                        x=df_yest['time_str'], y=df_yest['cum_vol'], 
                        fill='tozeroy', mode='lines', name='Hôm qua', 
                        line=dict(color='rgba(65, 105, 225, 0.6)', width=2), 
                        fillcolor='rgba(65, 105, 225, 0.1)'
                    ))
                    fig_liq.add_trace(go.Scatter(
                        x=df_today['time_str'], y=df_today['cum_vol'], 
                        fill='tozeroy', mode='lines', name='Hôm nay', 
                        line=dict(color='rgba(154, 205, 50, 0.9)', width=2), 
                        fillcolor='rgba(154, 205, 50, 0.5)'
                    ))
                    fig_liq.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10), 
                        height=350, hovermode="x unified", 
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_liq, use_container_width=True)

                with col2:
                    st.markdown("#### 🎯 Tác động tới VN-INDEX (Chuẩn Vốn Hóa)")
                    # Tính năng Truyền điểm VN-INDEX hôm qua vào để tự tính chuẩn xác
                    df_contrib = get_exact_contribution(df_top100, ref_price_index)
                    
                    if not df_contrib.empty:
                        top_pos = df_contrib[df_contrib['Điểm'] > 0].sort_values(by='Điểm', ascending=False).head(10)
                        top_neg = df_contrib[df_contrib['Điểm'] < 0].sort_values(by='Điểm', ascending=True).head(10)
                        
                        df_impact = pd.concat([top_pos, top_neg]).sort_values(by='Điểm', ascending=False)
                        bar_colors = [COLOR
