import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import re

# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS LÀM MƯỢT UI
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 15px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d') # Dành cho MA20

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

# Thanh Header mượt mà
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: st.warning(f"🔴 ĐÃ ĐÓNG CỬA | {end_date}")
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 3. MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

# BỘ GIẢ LẬP TRÌNH DUYỆT (CHỐNG BỊ CHẶN IP KHI ĐANG GIAO DỊCH)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

# 4. HÀM LẤY DỮ LIỆU TỐI ƯU (KHÔNG DÙNG LUỒNG QUÉT 400 MÃ NỮA)
@st.cache_data(ttl=60)
def get_market_data():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        df = pd.DataFrame(res['data'])[['ticker','price','priceChange','percentPriceChange','volume']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
        return df.sort_values('Tổng KL', ascending=False).head(100)
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        d = pd.DataFrame(requests.get(url, headers=HEADERS, timeout=5).json()['data'])
        return d[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef_reports():
    res = []
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", headers=HEADERS, timeout=10).text
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res.append({"Ngày": (re.search(r'class="doc_date".*?>(.*?)</span>', b) or re.search('','')).group(1) or "", "Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1) or "", "CTCK": (re.search(r'class="doc_source".*?>(.*?)</span>', b) or re.search('','')).group(1) or "", "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
    except: pass
    return pd.DataFrame(res)

# 5. HIỂN THỊ GIAO DIỆN
with st.spinner("Đang tải dữ liệu Real-time an toàn..."):
    df_100 = get_market_data()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_cafef_reports()

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
                    df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig = go.Figure()
                    if len(dates) > 1: fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Hôm qua', line=dict(color='rgba(150,150,150,0.5)')))
                    fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Hôm nay', line=dict(color=C_GREEN)))
                    fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h", y=1.1), plot_bgcolor='rgba(0,0,0,0)')
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown("#### 🎯 Tác động tới VN-INDEX")
                    df_c = get_index_contrib()
                    if not df_c.empty:
                        df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                        b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                        fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_b, use_container_width=True)
        except: st.error("Đang cập nhật biểu đồ thanh khoản trong ngày...")

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: st.warning("Đang chờ dữ liệu dòng tiền...")

with t3:
    if not df_100.empty:
        def style_v(v):
            if v >= 6.8: c = C_CEIL
            elif v <= -6.8: c = C_FLOOR
            elif v > 0: c = C_GREEN
            elif v == 0: c = C_REF
            elif v > -3: c = C_RED
            else: c = C_DRED
            return f'color: {c}; font-weight: bold;'
        st.markdown("### Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất")
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

with t4:
    if not df_reports.empty:
        if not df_100.empty: df_reports = pd.merge(df_reports, df_100[['Mã CK', 'Giá']], on='Mã CK', how='left')
        st.markdown("### 📝 Tổng hợp Báo Cáo Phân Tích (CafeF)")
        st.dataframe(df_reports.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v).upper() else C_RED if "BÁN" in str(v).upper() else C_REF}; font-weight:bold;', subset=['Khuyến nghị']).format({'Giá': '{:,.2f}'}), column_config={"Link": st.column_config.LinkColumn("Tài liệu")}, hide_index=True, use_container_width=True, height=600)
    else: st.warning("CafeF chưa cập nhật báo cáo mới hoặc đang chặn kết nối.")

with t5:
    if not df_idx_daily.empty and not df_100.empty:
        c, ma, v, v_ma = df_idx_daily.iloc[-1]['close'], df_idx_daily.iloc[-1]['MA20'], df_idx_daily.iloc[-1]['volume'], df_idx_daily.iloc[-1]['V_MA20']
        adv, dec = len(df_100[df_100['%'] > 0]), len(df_100[df_100['%'] < 0])
        score = sum([c > ma, v > v_ma, adv > dec])
        
        cols = [C_RED, C_REF, C_GREEN, C_CEIL]
        txts = ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"]
        
        st.markdown(f"""
        <div class='card'>
            <h2 style='color:{cols[score]}; margin-top:0;'>{txts[score]} ({score}/3 Điểm)</h2>
            <p style='font-size: 16px;'><b>1. Kỹ thuật:</b> Giá VN-INDEX ({c:,.2f}) đang {'nằm trên' if c > ma else 'rơi xuống dưới'} MA20 ({ma:,.2f}).</p>
            <p style='font-size: 16px;'><b>2. Dòng tiền:</b> Khối lượng thị trường {'vượt qua' if v > v_ma else 'thấp hơn'} mức trung bình 20 phiên.</p>
            <p style='font-size: 16px;'><b>3. Cung - Cầu:</b> Sắc xanh {'áp đảo' if adv > dec else 'yếu thế'} (Tăng: {adv} mã | Giảm: {dec} mã).</p>
            <hr style='border-color: #3f3f5a;'>
            <h4 style='margin-bottom:0;'>👉 GỢI Ý HÀNH ĐỘNG: <span style='color:{C_GREEN if score >= 2 else C_RED}'>{'Ưu tiên giải ngân, gia tăng tỷ trọng.' if score >= 2 else 'Phòng thủ, hạ tỷ trọng Margin, đứng ngoài quan sát.'}</span></h4>
        </div>
        """, unsafe_allow_html=True)
