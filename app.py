import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
import requests, pytz
from datetime import datetime, timedelta

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>.card{background:#1e1e2f;padding:15px;border-radius:10px;border-left:5px solid #ffaa00;color:white;}</style>", unsafe_allow_html=True)

tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz)

col1, col2 = st.columns([4, 1])
col1.title(f"🧚‍♀️ FAIRY INVEST - REAL TIME {now.strftime('%d/%m')}")
if col2.button("🔄 Cập nhật Live", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 2. HÀM GỌI API LÕI (Bypass hoàn toàn vnstock, không bao giờ lỗi Import)
@st.cache_data(ttl=60)
def get_live_data():
    try:
        # 1. Lấy Bảng giá Top 100 từ TCBS
        url_board = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        d_100 = requests.get(url_board, headers={'User-Agent': 'Mozilla'}, timeout=10).json()['data']
        df_board = pd.DataFrame(d_100)[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'}).sort_values('KL', ascending=False).head(100)
        
        # 2. Lấy Chỉ số VN-INDEX lịch sử từ DNSE (Chính là nguồn ngầm của vnstock)
        e_t, s_t = int(now.timestamp()), int((now - timedelta(days=60)).timestamp())
        url_idx = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/index?ticker=VNINDEX&resolution=1D&from={s_t}&to={e_t}"
        d_idx = requests.get(url_idx, timeout=10).json()
        df_idx = pd.DataFrame({'time': pd.to_datetime(d_idx['t'], unit='s', utc=True).dt.tz_convert('Asia/Ho_Chi_Minh'), 'close': d_idx['c'], 'volume': d_idx['v']})
        df_idx['MA20'], df_idx['V_MA20'] = df_idx['close'].rolling(20).mean(), df_idx['volume'].rolling(20).mean()
        
        return df_board, df_idx.dropna().reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ Lỗi mạng từ Streamlit: {e}")
        return pd.DataFrame(), pd.DataFrame()

with st.spinner("Đang nạp dữ liệu Real-time từ Sàn..."):
    d_board, d_idx = get_live_data()

# 3. HIỂN THỊ 4 TAB TINH GỌN
t1, t2, t3, t4 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "🔮 Kịch bản AI"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX (Live)", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t2:
    if not d_board.empty:
        st.plotly_chart(px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0, '#00e5ff'], [0.5, '#f5b041'], [1, '#cc00ff']], range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t3:
    if not d_board.empty:
        st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}).map(lambda v: f'color: {"#00e676" if v>0 else "#ff4d4d" if v<0 else "#f5b041"}', subset=['%']), hide_index=True, use_container_width=True)

with t4:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3 Điểm)</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'dưới'} TB | Tăng:{adv}/Giảm:{dec}</p><hr><p>👉 <b>Hành động:</b> {'Gia tăng tỷ trọng' if sc>=2 else 'Quản trị rủi ro'}</p></div>", unsafe_allow_html=True)
