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

# 2. HÀM GỌI API LÕI VỚI CHẾ ĐỘ TÀNG HÌNH (VƯỢT TƯỜNG LỬA)
@st.cache_data(ttl=60)
def get_live_data():
    df_board, df_idx = pd.DataFrame(), pd.DataFrame()
    
    # Giả lập 100% trình duyệt Chrome thật để không bị TCBS chặn IP
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://tcinvest.tcbs.com.vn',
        'Referer': 'https://tcinvest.tcbs.com.vn/'
    }
    
    try:
        # LẤY DỮ LIỆU TCBS
        res_tcbs = requests.get("https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE", headers=headers, timeout=10)
        if res_tcbs.status_code == 200:
            data_json = res_tcbs.json()
            if 'data' in data_json:
                df_board = pd.DataFrame(data_json['data'])[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'}).sort_values('KL', ascending=False).head(100)
            else:
                st.error("❌ TCBS đổi cấu trúc dữ liệu, không tìm thấy mục 'data'.")
        else:
            st.error(f"❌ Máy chủ Streamlit bị TCBS chặn. Mã lỗi: {res_tcbs.status_code}")

        # LẤY CHỈ SỐ VN-INDEX TỪ DNSE (Nguồn ngầm của vnstock)
        e_t, s_t = int(now.timestamp()), int((now - timedelta(days=60)).timestamp())
        res_idx = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/index?ticker=VNINDEX&resolution=1D&from={s_t}&to={e_t}", headers=headers, timeout=10)
        if res_idx.status_code == 200:
            d_idx = res_idx.json()
            if 't' in d_idx:
                df_idx = pd.DataFrame({'time': pd.to_datetime(d_idx['t'], unit='s', utc=True).dt.tz_convert('Asia/Ho_Chi_Minh'), 'close': d_idx['c'], 'volume': d_idx['v']})
                df_idx['MA20'], df_idx['V_MA20'] = df_idx['close'].rolling(20).mean(), df_idx['volume'].rolling(20).mean()
                df_idx = df_idx.dropna().reset_index(drop=True)
            
    except Exception as e:
        st.error(f"❌ Lỗi mạng gián đoạn: {e}")
        
    return df_board, df_idx

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
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({
