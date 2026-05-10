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
# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS TÙY CHỈNH
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    /* Chỉnh thẻ Metric và Bảng */
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    
    /* Giao diện Tab 5 (Kịch bản) */
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
    .prob-badge { background-color: #33334d; padding: 3px 8px; border-radius: 5px; font-weight: bold; color: #ffaa00; }
    
    /* BIẾN RADIO BUTTON CỦA STREAMLIT THÀNH MENU BÊN PHẢI TUYỆT ĐẸP */
    div.row-widget.stRadio > div { flex-direction: column; gap: 10px; }
    div.row-widget.stRadio > div > label {
        background-color: #2a2a3c; color: white; padding: 12px 15px;
        border-radius: 8px; border: 1px solid #3f3f5a;
        cursor: pointer; transition: 0.3s; width: 100%; margin: 0;
    }
    div.row-widget.stRadio > div > label:hover { background-color: #3f3f5a; border-color: #ffaa00; }
    /* Trạng thái được chọn */
    div.row-widget.stRadio > div > label[data-checked="true"] { background-color: #ffaa00; color: #1e1e2f; font-weight: bold; border: none; }
    /* Ẩn dấu chấm tròn mặc định của Radio */
    div.row-widget.stRadio > div > label > div:first-child { display: none; }
    div.row-widget.stRadio > div > label > div:nth-child(2) { font-size: 16px; margin-left: 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_stock = (now - timedelta(days=7)).strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.toast("Đã làm mới dữ liệu!", icon="✅")

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU TỐI ƯU
# ==========================================
@st.cache_data(ttl=86400)
def get_hose_tickers():
    try:
        df = listing_companies()
        return df[df['comGroupCode'] == 'HOSE']['ticker'].head(150).tolist()
    except: return ['VCB', 'VHM', 'VIC', 'FPT', 'HPG', 'SSI', 'VND']

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {'Mã CK': t, 'Giá hiện tại': curr, '+/-': round(curr-prev, 2), '%': round((curr-prev)/prev*100, 2), 'Tổng KL': int(d.iloc[-1]['volume'])}
        except: return None
    # CHỐNG TRÀN RAM: Giảm luồng tải xuống mức 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
        res = list(exe.map(fetch, tickers))
    df = pd.DataFrame([r for r in res if r])
    return df.sort_values('Tổng KL', ascending=False).head(100) if not df.empty else df

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            d = pd.DataFrame(r.json()['data'])
            return d[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_rss_reports():
    # SỬ DỤNG NGUỒN RSS FEED: Không bao giờ bị chặn bởi tường lửa Cloudflare
    reports = []
    try:
        url = "https://vietstock.vn/rss/phan-tich-nhan-dinh.vi"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, 'xml')
        
        for item in soup.find_all('item')[:30]:
            title = item.title.text
            link = item.link.text
            pubDate = item.pubDate.text
            
            ticker_match = re.search(r'([A-Z0-9]{3})\s*:', title)
            ticker = ticker_match.group(1) if ticker_match else "Thị trường"
            action_match = re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN|TÍCH LŨY|TRUNG LẬP)', title, re.IGNORECASE)
            action = action_match.group(1).upper() if action_match else "ĐÁNH GIÁ"
            
            reports.append({"Ngày": pubDate[5:16], "Mã CK": ticker, "Khuyến nghị": action, "Tiêu đề Báo cáo": title, "Link": link})
    except: pass
    return pd.DataFrame(reports)

@st.cache_data(ttl=300)
def get_vnindex_history():
    try:
        start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['Vol_MA20'] = df['volume'].rolling(window=20).mean()
        return df
    except: return pd.DataFrame()

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
df_100 = get_market_data()
t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Khuyến Nghị CTCK", "🔮 Chiến lược Giao dịch"])

# --- TAB 1, 2, 3 ---
with t1:
    try:
        df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
        cur, ref = df_daily.iloc[-1]['close'], df_daily.iloc[-2]['close']
        st.metric(f"Điểm số VN-INDEX", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌊 Thanh khoản")
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                dates = pd.to_datetime(df_idx['time']).dt.date.unique()
                df_t = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-1]].copy()
                df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                fig = go.Figure()
                if len(dates) >= 2:
                    df_y = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-2]].copy()
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Phiên trước', line=dict(color='rgba(150,150,150,0.5)')))
                fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Hôm nay', line=dict(color=C_GREEN)))
                fig.update_layout(height=380, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### 🎯 Tác động tới VN-INDEX")
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=[C_GREEN if v>0 else C_RED for v in df_res['Điểm']], text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig_b, use_container_width=True)
    except: st.info("Hệ thống biểu đồ đang tải...")

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_100.empty:
        def style_v(v): return f'color: {C_CEIL if v>=6.8 else C_FLOOR if v<=-6.8 else C_GREEN if v>0 else C_RED if v<0 else C_REF}; font-weight: bold;'
        st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True)

# --- TAB 4: BÁO CÁO PHÂN TÍCH (RSS FEED - KHÔNG BAO GIỜ LỖI) ---
with t4:
    st.markdown("### 📝 Báo Cáo & Nhận Định (Nguồn: Vietstock)")
    df_rep = get_rss_reports()
    if not df_rep.empty:
        def s_act(val): return f'color: {C_GREEN if "MUA" in str(val) or "KHẢ" in str(val) else C_RED if "BÁN" in str(val) else C_REF}; font-weight: bold;'
        st.dataframe(df_rep.style.map(s_act, subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Tài liệu", display_text="🔗 Xem bài")}, use_container_width=True, hide_index=True, height=600)
    else: st.warning("Đang tải dữ liệu tin tức...")

# --- TAB 5: CHIẾN LƯỢC GIAO DỊCH (TƯƠNG TÁC THẬT) ---
with t5:
    col_content, col_menu = st.columns([7, 3])
    df_hist = get_vnindex_history()
    
    with col_menu:
        st.markdown("<h4 style='color: white;'>📑 Menu Phân Tích</h4>", unsafe_allow_html=True)
        # Khai báo Radio button thực sự để bắt sự kiện click
        tab5_option = st.radio("Chọn chức năng:", ["🔮 Chiến lược What-if", "📈 Xu hướng Giá", "📊 Xu hướng Khối lượng", "⚖️ Cung - Cầu"], label_visibility="collapsed")

    with col_content:
        if df_hist.empty or df_100.empty:
            st.warning("Đang kết nối dữ liệu phân tích...")
        else:
            cur_close = df_hist.iloc[-1]['close']
            ma20 = df_hist.iloc[-1]['MA20']
            is_uptrend = cur_close > ma20
            trend_color = C_GREEN if is_uptrend else C_RED
            trend_txt = "TÍCH CỰC" if is_uptrend else "TIÊU CỰC"

            if tab5_option == "🔮 Chiến
