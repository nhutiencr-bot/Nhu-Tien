import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
import plotly.express as px
import requests
import time

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN & TỐI ƯU CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# Thiết lập Múi giờ
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: st.warning(f"🔴 ĐÃ ĐÓNG CỬA | {now.strftime('%Y-%m-%d')}")
    if st.button("🔄 Cập nhật dữ liệu", use_container_width=True):
        st.cache_data.clear()

# Bảng Màu Chuẩn
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# 2. LÕI DỮ LIỆU SIÊU TỐC (CHỐNG LAG TUYỆT ĐỐI)
# ==========================================
@st.cache_data(ttl=15)
def get_live_market_data():
    """Lấy Bảng giá 100 mã tác động lớn nhất (Tốc độ: 0.2s)"""
    try:
        url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE&size=100&_t={int(time.time())}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            res = [{'Mã CK': i.get('code'), 'Giá': i.get('matchPrice', 0), '+/-': i.get('priceChange', 0), '%': i.get('changePc', 0), 'Tổng KL': i.get('accumulatedVol', 0)} for i in r.json()['data']]
            return pd.DataFrame(res)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_live_index_chart():
    """Lấy Dữ liệu Biểu đồ VNINDEX 1 phút (Bao gồm ATC đến 15:00)"""
    try:
        ts_now = int(time.time())
        ts_start = ts_now - (5 * 86400) # Lùi 5 ngày để chắc chắn lấy được "Hôm qua"
        url = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=1&symbol=VNINDEX&from={ts_start}&to={ts_now}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        data = r.json()
        if data.get('s') == 'ok':
            return pd.DataFrame({
                'time': [datetime.fromtimestamp(t, vn_tz) for t in data['t']],
                'close': data['c'], 'volume': data['v']
            })
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    """Lấy dữ liệu Tác động VN-INDEX (Tốc độ: 0.1s)"""
    try:
        url = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX&_t={int(time.time())}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            return pd.DataFrame(r.json()['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    return pd.DataFrame()

# ==========================================
# 3. RENDER GIAO DIỆN (UI)
# ==========================================
with st.spinner("Đang tải dữ liệu băng thông rộng..."):
    df_100 = get_live_market_data()
    df_idx = get_live_index_chart()
    df_c = get_index_contrib()

t1, t2, t3 = st.tabs(["📈 VN-INDEX & Thanh Khoản", "🗺️ Bản đồ Dòng tiền", "📊 Bảng Giá Top 100"])

with t1:
    if not df_idx.empty:
        # Xử lý tách ngày "Hôm nay" và "Hôm qua" chuẩn xác
        df_idx['date'] = df_idx['time'].dt.date
        unique_dates = df_idx['date'].unique()
        
        if len(unique_dates) >= 2:
            df_today = df_idx[df_idx['date'] == unique_dates[-1]].copy()
            df_yest = df_idx[df_idx['date'] == unique_dates[-2]].copy()
            
            c, p = df_today.iloc[-1]['close'], df_yest.iloc[-1]['close']
            latest_time_str = df_today.iloc[-1]['time'].strftime('%H:%M:%S')
            
            st.metric(f"VN-INDEX (Cập nhật: {latest_time_str})", f"{c:,.2f}", f"{c-p:+,.2f} ({((c-p)/p*100):+,.2f}%)")
            st.divider()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🌊 Thanh khoản (Hôm nay vs Hôm qua)")
                
                # Format thời gian trục X thành String (HH:MM) để đồng bộ 2 ngày
                df_today['ts'] = df_today['time'].dt.strftime('%H:%M')
                df_yest['ts'] = df_yest['time'].dt.strftime('%H:%M')
                
                # Tính tổng thanh khoản cộng dồn (Cumulative Volume)
                df_today['cum_vol'] = df_today['volume'].cumsum()
                df_yest['cum_vol'] = df_yest['volume'].cumsum()
                
                # VẼ BIỂU ĐỒ GIỐNG HỆT ẢNH BẠN YÊU CẦU
                fig_liq = go.Figure()
                
                # Đường Hôm qua (Line Xanh dương, không fill)
                fig_liq.add_trace(go.Scatter(
                    x=df_yest['ts'], y=df_yest['cum_vol'], 
                    mode='lines', name='Hôm qua', 
                    line=dict(color='#5c6bc0', width=2)
                ))
                
                # Đường Hôm nay (Fill Xanh lá mạ giống ảnh)
                fig_liq.add_trace(go.Scatter(
                    x=df_today['ts'], y=df_today['cum_vol'], 
                    mode='lines', name='Hôm nay', 
                    fill='tozeroy', fillcolor='rgba(156, 204, 101, 0.6)', 
                    line=dict(color='#7cb342', width=2)
                ))
                
                fig_liq.update_layout(
                    height=380, margin=dict(l=0, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    plot_bgcolor='white', hovermode='x unified'
                )
                fig_liq.update_xaxes(showgrid=True, gridcolor='#f0f0f0', nticks=10)
                fig_liq.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
                st.plotly_chart(fig_liq, use_container_width=True)
                
            with col2:
                st.markdown("#### 🎯 Tác động tới VN-INDEX")
                if not df_c.empty:
                    df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                    fig_b = go.Figure(go.Bar(
                        x=df_res['Mã CK'], y=df_res['Điểm'], 
                        marker_color=[C_GREEN if v > 0 else C_RED for v in df_res['Điểm']], 
                        text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'
                    ))
                    fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='white')
                    fig_b.add_hline(y=0, line_width=1, line_color="#d0d0d0")
                    fig_b.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
                    st.plotly_chart(fig_b, use_container_width=True)

with t2:
    if not df_100.empty:
        # Bổ sung cột ảo 'Thị trường' để vẽ Treemap
        df_100['Thị trường'] = 'VN-INDEX'
        fig_m = px.treemap(df_100, path=['Thị trường', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        fig_m.update_layout(height=650, margin=dict(t=0,l=0,r=0,b=0))
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
        
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

if is_trading:
    time.sleep(30) # Kéo giãn thời gian lặp để UI mượt mà, không bị chớp giật
    st.rerun()
