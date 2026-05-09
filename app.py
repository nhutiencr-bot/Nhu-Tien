import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests

# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
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
    if is_trading:
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else:
        st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.toast("Đã làm mới dữ liệu thị trường!", icon="✅")

# 3. MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

# 4. HÀM LẤY DỮ LIỆU
@st.cache_data(ttl=300)
def get_hose_tickers():
    try:
        df = listing_companies()
        return df[df['comGroupCode'] == 'HOSE']['ticker'].tolist()
    except: return []

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {
                'Mã CK': t, 'Giá': curr, '+/-': round(curr-prev, 2),
                '%': round((curr-prev)/prev*100, 2), 
                'Tổng KL': int(d.iloc[-1]['volume'])
            }
        except: return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
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

# 5. HIỂN THỊ GIAO DIỆN
with st.spinner("Đang tính toán dữ liệu thị trường..."):
    df_100 = get_market_data()

t1, t2, t3 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu"])

with t1:
    with st.spinner("Đang vẽ biểu đồ VN-INDEX..."):
        try:
            # Lấy dữ liệu 1 phút (Cho biểu đồ) và dữ liệu Ngày (Cho giá tham chiếu)
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
            
            if not df_idx.empty and not df_daily.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                
                # Phiên gần nhất
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                
                cur = df_t.iloc[-1]['close']
                # Lấy giá đóng cửa phiên trước làm tham chiếu (rất ổn định)
                ref = df_daily.iloc[-2]['close'] if len(df_daily) >= 2 else df_t.iloc[0]['close']
                
                st.metric(f"Điểm số VN-INDEX (Lúc {df_t.iloc[-1]['time']})", f"{cur:,.2f}", 
                          f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🌊 Thanh khoản")
                    df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                    fig = go.Figure()
                    
                    # Logic thông minh: Nếu API còn giữ dữ liệu phiên trước thì vẽ thêm đường mờ
                    if len(dates) >= 2:
                        df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                        df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                        fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Phiên trước', line=dict(color='rgba(150,150,150,0.5)')))
                    
                    fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Phiên gần nhất', line=dict(color=C_GREEN)))
                    fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h", y=1.1), plot_bgcolor='rgba(0,0,0,0)')
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown("#### 🎯 Tác động tới VN-INDEX")
                    df_c = get_index_contrib()
                    if not df_c.empty:
                        df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), 
                                           df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                        b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                        fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, 
                                                 text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        fig_b.add_hline(y=0, line_width=1, line_color="black")
                        st.plotly_chart(fig_b, use_container_width=True)
        except Exception as e: 
            st.error("Tạm thời không tải được dữ liệu biểu đồ. API hệ thống ngoài giờ có thể đang dọn dẹp bộ nhớ.")

with t2:
    if not df_100.empty:
        with st.spinner("Đang kết xuất Bản đồ Dòng tiền..."):
            fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', 
                               color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
            fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
            fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0))
            st.plotly_chart(fig_m, use_container_width=True)

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
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'})
                     .map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)
