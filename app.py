import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies, ticker_overview
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests

# --- 1. CÀI ĐẶT GIAO DIỆN ---
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# --- 2. THIẾT LẬP THỜI GIAN ---
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_stock = (now - timedelta(days=7)).strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')

# Kiểm tra giờ giao dịch
is_trading = (now.weekday() < 5) and (
    (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30)
)

if is_trading:
    st.sidebar.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M:%S')}")
else:
    st.sidebar.warning(f"🔴 ĐÃ ĐÓNG CỬA | Chốt phiên: {end_date}")

# --- 3. KHAI BÁO MÀU SẮC CHUẨN ---
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

# --- 4. HÀM LẤY DỮ LIỆU ---
@st.cache_data(ttl=86400)
def get_sectors():
    try:
        df = listing_companies()
        mask = (df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)
        return df[mask][['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=300)
def get_top_100():
    sec_dict = get_sectors()
    tickers = list(sec_dict.keys())
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            c, p = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {
                'Mã CK': t, 'Ngành': sec_dict.get(t, 'Khác'), 'Giá': c,
                '+/-': round(c-p, 2), '%': round((c-p)/p*100, 2),
                'Tổng KL': int(d.iloc[-1]['volume'])
            }
        except: return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        res = [f.result() for f in [exe.submit(fetch, t) for t in tickers]]
    df = pd.DataFrame([r for r in res if r])
    return df.sort_values('Tổng KL', ascending=False).head(100) if not df.empty else df

@st.cache_data(ttl=86400)
def get_shares(tickers):
    def fetch_s(t):
        try: return t, ticker_overview(t)['outstandingShare'].iloc[0]
        except: return t, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
        res = [f.result() for f in [exe.submit(fetch_s, t) for t in tickers]]
    return {t: s for t, s in res if s > 0}

@st.cache_data(ttl=60)
def get_contrib(df_top, idx_ref):
    # API TCBS
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            d = pd.DataFrame(r.json()['data'])
            return d[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    # Fallback: Tự tính theo vốn hóa
    if not df_top.empty and idx_ref > 0:
        df = df_top.copy()
        sh = get_shares(df['Mã CK'].tolist())
        df['Cap'] = (df['Giá'] - df['+/-']) * df['Mã CK'].map(sh).fillna(0)
        df['Weight'] = df['Cap'] / (df['Cap'].sum() / 0.8)
        df['Điểm'] = idx_ref * df['Weight'] * (df['%'] / 100)
        return df[['Mã CK', 'Điểm']]
    return pd.DataFrame()

# --- 5. GIAO DIỆN ---
df_100 = get_top_100()
t1, t2, t3 = st.tabs(["📈 VN-INDEX", "🗺️ Bản đồ dòng tiền", "📊 Top 100 Active"])

with t1:
    try:
        df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
        if not df_idx.empty:
            df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
            dates = df_idx['date'].unique()
            df_t = df_idx[df_idx['date'] == dates[-1]].copy()
            df_y = df_idx[df_idx['date'] == dates[-2]].copy()
            cur, ref = df_t.iloc[-1]['close'], df_y.iloc[-1]['close']
            st.metric(f"VN-INDEX ({df_t.iloc[-1]['time']})", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🌊 Thanh khoản")
                df_t['ts'], df_y['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M'), pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Hôm qua', line=dict(color='gray')))
                fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Hôm nay', line=dict(color='green')))
                fig.update_layout(height=350, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.markdown("#### 🎯 Đóng góp điểm số")
                df_c = get_contrib(df_100, ref)
                if not df_c.empty:
                    df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                    # Sửa lỗi ngắt dòng màu sắc
                    b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                    fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                    fig_b.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0))
                    st.plotly_chart(fig_b, use_container_width=True)
    except: st.error("Đang kết nối dữ liệu...")

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Ngành', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        fig_m.update_layout(height=550, margin=dict(t=0,l=0,r=0,b=0))
        st.plotly_chart(fig_m, use_container_width=True)
        # Legend rút gọn
        st.markdown(f'<div style="display: flex; justify-content: center; gap: 10px; font-size: 12px;">'
                    f'<span><b style="color:{C_CEIL}">■</b> Trần</span> <span><b style="color:{C_GREEN}">■</b> Tăng</span> '
                    f'<span><b style="color:{C_REF}">■</b> Tham chiếu</span> <span><b style="color:{C_RED}">■</b> Giảm</span> '
                    f'<span><b style="color:{C_DRED}">■</b> Giảm sâu</span> <span><b style="color:{C_FLOOR}">■</b> Sàn</span></div>', unsafe_allow_html=True)

with t3:
    if not df_100.empty:
        def style_v(v):
            if v >= 6.8: c = C_CEIL
            elif v <= -6.8: c = C_FLOOR
            elif v > 0: c = C_GREEN
            elif v == 0: c = C_REF
            elif v > -3: c = C_RED
            else: c = C_DRED
            return f'color: {c}; font-weight: bold'
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

if is_trading:
    time.sleep(60)
    st.rerun()
