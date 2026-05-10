import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS (UI/UX)
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; margin-bottom: 20px; }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOGIC CHỌN NGÀY "BẤT TỬ" (GIẢI QUYẾT LỖI TRỐNG DỮ LIỆU)
# ==========================================
def get_trading_context():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.now(vn_tz)
    
    # Giả định giờ đóng cửa là 15:30
    is_after_market = now.hour > 15 or (now.hour == 15 and now.minute > 30)
    is_before_market = now.hour < 9
    
    # Xác định ngày lấy dữ liệu (Effective Date)
    target_date = now
    
    # Nếu là Thứ 7 (5) hoặc Chủ Nhật (6)
    if now.weekday() == 5: 
        target_date = now - timedelta(days=1)
    elif now.weekday() == 6: 
        target_date = now - timedelta(days=2)
    # Nếu là ngày thường nhưng chưa mở cửa hoặc vừa đóng cửa
    elif is_before_market:
        if now.weekday() == 0: # Sáng Thứ 2
            target_date = now - timedelta(days=3)
        else:
            target_date = now - timedelta(days=1)
            
    return target_date.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'), (now.weekday() < 5 and not is_before_market and not is_after_market)

trade_date, current_time, is_live = get_trading_context()

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST")
with col_status:
    if is_live:
        st.success(f"🟢 ĐANG GIAO DỊCH | {current_time}")
    else:
        st.warning(f"🔴 THỊ TRƯỜNG ĐÓNG | Phiên: {trade_date}")

C_CEIL, C_GREEN, C_REF, C_RED, C_DRED, C_FLOOR = '#cc00ff', '#00e676', '#f5b041', '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# 3. HÀM LẤY DỮ LIỆU (DÙNG API TCBS & RSS VIETSTOCK)
# ==========================================
@st.cache_data(ttl=300)
def get_data_snapshot():
    try:
        # Lấy dữ liệu Snapshot từ TCBS (Rất ổn định, ít bị chặn IP)
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        df = pd.DataFrame(r.json()['data'])
        df = df[['ticker', 'price', 'priceChange', 'percentPriceChange', 'volume']].copy()
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
        return df.sort_values('Tổng KL', ascending=False).head(100)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_news_rss():
    news = []
    try:
        r = requests.get("https://vietstock.vn/rss/phan-tich-nhan-dinh.vi", timeout=10)
        soup = BeautifulSoup(r.content, 'xml')
        for item in soup.find_all('item')[:15]:
            title = item.title.text
            news.append({
                "Ngày": item.pubDate.text[5:16],
                "Mã": (re.search(r'([A-Z0-9]{3})\s*:', title) or re.search('', '')).group(0) or "Tin chung",
                "Tiêu đề": title,
                "Link": item.link.text
            })
    except: pass
    return pd.DataFrame(news)

# ==========================================
# 4. HIỂN THỊ CÁC TABS
# ==========================================
df_m = get_data_snapshot()
t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX", "🗺️ Dòng tiền", "📊 Top 100", "📝 Tin tức", "🔮 Chiến lược"])

with t1:
    try:
        # Lấy lịch sử VNINDEX để vẽ biểu đồ
        hist = stock_historical_data('VNINDEX', (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'), trade_date, '1D', 'index')
        if not hist.empty:
            cur, ref = hist.iloc[-1]['close'], hist.iloc[-2]['close']
            st.metric("VN-INDEX", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
            fig = px.area(hist, x='time', y='close', title='Diễn biến VN-INDEX')
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
    except: st.info("Đang cập nhật dữ liệu chỉ số...")

with t2:
    if not df_m.empty:
        fig_m = px.treemap(df_m, path=[px.Constant("HOSE"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_m.empty:
        st.dataframe(df_m.style.format({'Giá': '{:,.2f}', '%': '{:+,.2f}%'}).map(lambda v: f'color: {C_GREEN if v>0 else C_RED}', subset=['%']), use_container_width=True, hide_index=True)

with t4:
    df_n = get_news_rss()
    if not df_n.empty:
        st.dataframe(df_n, column_config={"Link": st.column_config.LinkColumn("Tài liệu")}, use_container_width=True, hide_index=True)

with t5:
    st.markdown(f"""
    <div class="scenario-card">
        <div class="scenario-title">Dự báo chiến lược phiên {trade_date}</div>
        <p>Thị trường đang trong trạng thái <b>{'Tích cực' if not df_m.empty and df_m['%'].mean() > 0 else 'Thận trọng'}</b>.</p>
        <ul>
            <li>Quan sát dòng tiền tại các mã vốn hóa lớn.</li>
            <li>Hỗ trợ tâm lý: vùng giá kết phiên gần nhất.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
