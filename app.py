import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import xml.etree.ElementTree as ET

# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}

# 4. HÀM LẤY DỮ LIỆU TỪ VNDIRECT (CHỐNG CHẶN IP, CHUẨN FREE-FLOAT)
@st.cache_data(ttl=60)
def get_market_data():
    try:
        url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVol~DESC&q=floor:HOSE&size=100"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        df = pd.DataFrame(res['data'])[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
        df[['Giá', '+/-', '%', 'Tổng KL']] = df[['Giá', '+/-', '%', 'Tổng KL']].apply(pd.to_numeric)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=50"
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        df = pd.DataFrame(res['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef_rss():
    res = []
    try:
        # Dùng RSS của CafeF để lấy tin tức chuẩn 100% không bao giờ bị chặn
        xml_data = requests.get("https://cafef.vn/rss/chung-khoan.rss", headers=HEADERS, timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:30]:
            title = item.find('title').text
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            
            # Quét mã Chứng khoán trong tiêu đề
            match = re.search(r'\b([A-Z]{3})\b', title)
            ticker = match.group(1) if match else "Thị trường"
            action = "CHÚ Ý" if "mua" in title.lower() or "tăng" in title.lower() else "CẢNH BÁO" if "bán" in title.lower() or "giảm" in title.lower() else "TIN TỨC"
            
            res.append({"Ngày": pubDate[5:16], "Mã CK": ticker, "Đánh giá": action, "Tiêu đề Báo cáo": title, "Link": link})
    except: pass
    return pd.DataFrame(res)

# 5. HIỂN THỊ GIAO DIỆN
with st.spinner("Đang kết nối siêu tốc lấy Dữ liệu VNDirect..."):
    df_100 = get_market_data()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_cafef_rss()

t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Báo cáo CafeF", "🔮 AI Kịch Bản"])

with t1:
    with st.spinner("Đang vẽ biểu đồ VN-INDEX..."):
        try:
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                df_y = df_idx[df_idx['date'] == dates[-2]].copy() if len(dates) > 1 else df_t
                cur, ref = df_t.iloc[-1]['close'], df_y.iloc[-1]['close']
                
                st.metric(f"Điểm số VN-INDEX (Lúc {df_t.iloc[-1]['time']})", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🌊 Thanh khoản (Hôm nay vs Hôm qua)")
                    df_t['ts'] = pd.to_datetime(df
