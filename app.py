import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import urllib.parse
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .scenario-box { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Phân Tích Chuyên Sâu")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M:%S')}")
    else: st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    if st.button("🔄 Cập nhật Live", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_LRED, C_FLOOR = '#b30000', '#ff4d4d', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR],            
    [0.014, C_RED], [0.2857, C_RED],             
    [0.2857, C_LRED], [0.4992, C_LRED],          
    [0.4992, C_REF], [0.5007, C_REF],            
    [0.5007, C_GREEN], [0.9857, C_GREEN],        
    [0.9857, C_CEIL], [1.0, C_CEIL]              
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'}

# ==========================================
# 3. MẠNG PROXY XUYÊN TƯỜNG LỬA CHỐNG TRẮNG TRANG
# ==========================================
def fetch_url_with_proxies(target_url, is_json=True):
    encoded_url = urllib.parse.quote(target_url, safe='')
    urls_to_try = [
        target_url,
        f"https://api.codetabs.com/v1/proxy?quest={encoded_url}", # Proxy xịn nhất hiện nay
        f"https://api.allorigins.win/raw?url={encoded_url}"
    ]
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200 and len(res.content) > 50:
                return res.json() if is_json else res.text
        except: continue
    return None

@st.cache_data(ttl=30)
def get_top_200_realtime():
    """ Lấy động 200 mã Giá Trị Giao Dịch lớn nhất """
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=200"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol', 'accumulatedVal']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
        df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
        return df.dropna(subset=['Tổng KL'])
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    url = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=120)
def get_vnindex_live_and_ma():
    live_c, live_v = 0, 0
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:VNINDEX"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data and len(data['data']) > 0:
        live_c = float(data['data'][0].get('matchPrice', 0))
        live_v = float(data['data'][0].get('accumulatedVol', 0))
        
    try: # Hàm bất tử vnstock lấy MA20
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            last = df.iloc[-1]
            c = live_c if live_c > 0 else float(last['close'])
            v = live_v if live_v > 0 else float(last['volume'])
            p = float(df.iloc[-2]['close']) if len(df) > 1 else c
            return {'close': c, 'prev': p, 'volume': v, 'MA20': float(last['MA20']), 'V_MA20': float(last['V_MA20'])}
    except: pass
    return None

@st.cache_data(ttl=1800)
def get_cafef_reports():
    """ Trích xuất Khuyến Nghị đúng format MWG MUA giá mục tiêu... """
    url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    html = fetch_url_with_proxies(url, is_json=False)
    res = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b)
            l_m = re.search(r'href="(/Report/Download\.aspx\?id=[^"]+
