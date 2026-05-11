import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
from vnstock import stock_historical_data
import requests, pytz
from datetime import datetime, timedelta

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>.card{background:#1e1e2f;padding:15px;border-radius:10px;border-left:5px solid #ffaa00;color:white;}</style>", unsafe_allow_html=True)

# 2. XÁC ĐỊNH THỜI GIAN THỰC TẾ (REAL-TIME)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz)
end_date = now.strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

col1, col2 = st.columns([4, 1])
col1.title(f"🧚‍♀️ FAIRY INVEST - REAL TIME {now.strftime('%d/%m/%Y')}")
if col2.button("🔄 Làm mới 11/05", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 3. LẤY DỮ LIỆU THẬT 100% (KHÔNG DÙNG DỮ LIỆU GIẢ)
@st.cache_data(ttl=60)
def get_idx():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except Exception as e:
        st.error(f"❌ Lỗi tải VN-INDEX từ vnstock: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_board():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        d = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=15).json()['data']
        df = pd.DataFrame(d)[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'})
        return df.sort_values('KL', ascending=False).head(100)
    except Exception as e:
        st.error(f"❌ Lỗi tải Bảng giá Top 100: Mạng Streamlit Cloud đang bị chặn. Chi tiết: {e}")
        return pd.DataFrame()

with st.spinner("Đang tải dữ liệu Real-time..."):
    d_idx = get_idx()
    d_board = get_board()

# 4. HIỂN THỊ CÁC TAB CHÍNH
t1, t2, t3, t4 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "🔮 Kịch bản AI"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX (Live)", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t2:
    if not d_board.empty:
        st.plotly_chart(px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale='RdYlGn', range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t3:
    if not d_board.empty:
        st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}), hide_index=True, use_container_width=True)

with t4:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3 Điểm)</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'dưới'} TB | Tăng:{adv}/Giảm:{dec}</p></div>", unsafe_allow_html=True)
