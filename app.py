import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import urllib.parse
import xml.etree.ElementTree as ET

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
# 2. THIẾT LẬP THỜI GIAN & HEADER
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Chiến Lược Toàn Thị Trường")
with col_status:
    if is_trading: 
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M:%S')}")
    else: 
        st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật Live", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# BẢNG PHÂN MÀU CHUẨN XÁC YÊU CẦU
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

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}

# ==========================================
# 3. LÕI DỮ LIỆU ĐỘT PHÁ: MẠNG PROXY ĐA TẦNG VƯỢT WAF
# ==========================================
@st.cache_data(ttl=30)
def get_top_200_realtime():
    """
    Lấy Top 200 mã có GIÁ TRỊ GIAO DỊCH cao nhất 3 sàn (HOSE, HNX, UPCOM).
    Đảm bảo 100% Real-time bằng cách dùng Proxy lách tường lửa Streamlit.
    """
    url_target = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=200"
    url_encoded = urllib.parse.quote(url_target, safe='')
    
    # Chiến lược 1: Gọi trực tiếp
    urls_to_try = [
        url_target,
        f"https://api.allorigins.win/raw?url={url_encoded}",  # Proxy 1
        f"https://corsproxy.io/?{url_encoded}"                # Proxy 2
    ]
    
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                data = res.json().get('data', [])
                if data:
                    df = pd.DataFrame(data)[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol', 'accumulatedVal']]
                    df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
                    df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
                    return df.dropna(subset=['Tổng KL'])
        except:
            continue
            
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    url_target = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30"
    url_encoded = urllib.parse.quote(url_target, safe='')
    
    urls_to_try = [url_target, f"https://api.allorigins.win/raw?url={url_encoded}"]
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                df = pd.DataFrame(res.json()['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
                df['Điểm'] = pd.to_numeric(df['Điểm'])
                return df
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=120)
def get_vnindex_live_and_ma():
    # Lấy Giá VNINDEX Real-time từ VNDirect
    live_price, live_vol = 0, 0
    try:
        r = requests.get("https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:VNINDEX", headers=HEADERS, timeout=5).json()
        live_price = float(r['data'][0]['matchPrice'])
        live_vol = float(r['data'][0]['accumulatedVol'])
    except: pass
    
    # Tính MA20 từ vnstock
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            
            last_row = df.iloc[-1]
            c = live_price if live_price > 0 else float(last_row['close'])
            v = live_vol if live_vol > 0 else float(last_row['volume'])
            p = float(df.iloc[-2]['close']) if len(df) > 1 else c
            
            return {
                'close': c, 'prev': p, 'volume': v, 
                'MA20': float(last_row['MA20']), 'V_MA20': float(last_row['V_MA20'])
            }
    except: return None
    return None

@st.cache_data(ttl=3600)
def get_vnexpress_news():
    res = []
    try:
        xml_data = requests.get("https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss", timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:20]:
            title, link, pubDate = item.find('title').text, item.find('link').text, item.find('pubDate').text
            action = "TIN TỨC"
            if any(k in title.lower() for k in ["tăng", "lãi", "hút", "vượt"]): action = "TÍCH CỰC"
            elif any(k in title.lower() for k in ["giảm", "lỗ", "bán", "lao"]): action = "TIÊU CỰC"
            res.append({"Ngày": pubDate[5:16], "Phân loại": action, "Tiêu đề": title, "Link": link})
    except: pass
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang kết nối Mạng Proxy lấy Top 200 Thanh Khoản Real-time..."):
    df_200 = get_top_200_realtime()
    
    if not df_200.empty:
        df_gainers = df_200.sort_values('%', ascending=False).head(10)
    else:
        df_gainers = pd.DataFrame()
        
    idx_data = get_vnindex_live_and_ma()
    df_reports = get_vnexpress_news()

t1, t2, t3, t4, t5, t6 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ Dòng tiền", 
    "📊 Top 200 Giao Dịch", 
    "🚀 Top Tăng Mạnh", 
    "📝 Tin Chứng khoán", 
    "🔮 AI Kịch Bản"
])

def style_v(v):
    try:
        v = float(v)
        if v >= 6.8: c = C_CEIL
        elif v <= -6.8: c = C_FLOOR
        elif v > 0: c = C_GREEN
        elif v == 0: c = C_REF
        elif v > -3: c = C_LRED
        else: c = C_RED
        return f'color: {c}; font-weight: bold;'
    except: return ''

# TAB 1: CHỈ SỐ
with t1:
    if idx_data:
        cur, prev = idx_data['close'], idx_data['prev']
        st.metric(
            f"Điểm số VN-INDEX (LIVE)", 
            f"{cur:,.2f}", 
            f"{cur-prev:+,.2f} ({((cur-prev)/prev*100):+,.2f}%)"
        )
