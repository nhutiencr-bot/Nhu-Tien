import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from vnstock import stock_historical_data
import requests
import re
from datetime import datetime, timedelta
import pytz

# 1. CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>.card{background:#1e1e2f;padding:15px;border-radius:10px;border-left:5px solid #ffaa00;color:white;}</style>", unsafe_allow_html=True)

# 2. THỜI GIAN REAL-TIME
tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz)
end_date = now.strftime('%Y-%m-%d')
start_date = (now - timedelta(days=60)).strftime('%Y-%m-%d')

st.title(f"🧚‍♀️ FAIRY INVEST - Dashboard {now.strftime('%d/%m/%Y')}")

# 3. HÀM LẤY DỮ LIỆU
@st.cache_data(ttl=60)
def load_data():
    # Lấy VN-INDEX
    try:
        df_idx = stock_historical_data('VNINDEX', start_date, end_date, '1D', 'index')
        if not df_idx.empty:
            df_idx['MA20'] = df_idx['close'].rolling(20).mean()
            df_idx['V_MA20'] = df_idx['volume'].rolling(20).mean()
    except: df_idx = pd.DataFrame()

    # Lấy Top 100 từ TCBS (Giả lập trình duyệt)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get("https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE", headers=headers, timeout=10).json()
        df_board = pd.DataFrame(res['data'])[['ticker','price','priceChange','percentPriceChange','volume']]
        df_board.columns = ['Mã CK','Giá','+/-','%','KL']
        df_board = df_board.sort_values('KL', ascending=False).head(100)
    except: df_board = pd.DataFrame()

    # Lấy Báo cáo CafeF
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=20", headers=headers, timeout=10).text
        reports = []
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                reports.append({"Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1), "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
        df_rep = pd.DataFrame(reports)
    except: df_rep = pd.DataFrame()

    return df_idx, df_board, df_rep

# 4. HIỂN THỊ
d_idx, d_board, d_rep = load_data()

# Kiểm tra nếu vẫn bị chặn (chỉ xảy ra trên Cloud)
if d_board.empty:
    st.error("⚠️ Không thể kết nối dữ liệu. Nếu bạn đang dùng Streamlit Cloud, IP đã bị chặn. Hãy chạy file này trên máy tính cá nhân.")

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t2:
    if not d_board.empty:
        st.plotly_chart(px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale='RdYlGn', range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t3:
    if not d_board.empty:
        st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}), hide_index=True, use_container_width=True)

with t4:
    if not d_rep.empty:
        st.dataframe(d_rep, column_config={"Link": st.column_config.LinkColumn("Tải PDF")}, hide_index=True, use_container_width=True)

with t5:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        score = sum([c > ma, v > v_ma, adv > dec])
        col = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][score]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>Chấm điểm: {score}/3</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'thấp hơn'} TB 20 phiên | Tăng: {adv} - Giảm: {dec}</p></div>", unsafe_allow_html=True)
