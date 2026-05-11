import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
from vnstock import stock_historical_data
import requests, re, pytz
from datetime import datetime, timedelta

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>.card{background:#1e1e2f;padding:15px;border-radius:10px;border-left:5px solid #ffaa00;color:white;}</style>", unsafe_allow_html=True)

tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz)
end_date = now.strftime('%Y-%m-%d')
# Lấy đủ 60 ngày để tính MA20 chính xác
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

col1, col2 = st.columns([4, 1])
col1.title(f"🧚‍♀️ FAIRY INVEST - LIVE {now.strftime('%H:%M:%S')}")
if col2.button("🔄 Cập nhật 11/05", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 2. HÀM LẤY DỮ LIỆU TỔNG HỢP (REAL-TIME)
@st.cache_data(ttl=60)
def get_full_data():
    df_idx, df_board, df_rep = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # 1. Lấy Chỉ số VN-INDEX (Lịch sử + MA20)
    try:
        df_idx = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df_idx.empty:
            df_idx['MA20'] = df_idx['close'].rolling(20).mean()
            df_idx['V_MA20'] = df_idx['volume'].rolling(20).mean()
            df_idx = df_idx.dropna().reset_index(drop=True)
    except: pass

    # 2. Lấy Bảng giá & Dòng tiền Top 100 từ TCBS (Nguồn ổn định nhất lúc 9h sáng)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        res = requests.get(url, headers=headers, timeout=10).json()
        if 'data' in res:
            df_board = pd.DataFrame(res['data'])[['ticker','price','priceChange','percentPriceChange','volume']]
            df_board.columns = ['Mã CK','Giá','+/-','%','KL']
            df_board = df_board.sort_values('KL', ascending=False).head(100)
    except: pass

    # 3. Lấy Báo cáo khuyến nghị từ CafeF
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).text
        res_rep = []
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res_rep.append({
                    "Ngày": (re.search(r'class="doc_date".*?>(.*?)</span>', b) or re.search('','')).group(1) or "",
                    "Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1) or "",
                    "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ",
                    "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)
                })
        df_rep = pd.DataFrame(res_rep)
    except: pass

    return df_idx, df_board, df_rep

# 3. XỬ LÝ HIỂN THỊ
with st.spinner("Đang kết nối sàn giao dịch..."):
    d_idx, d_board, d_rep = get_full_data()

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.warning("⚠️ Đang chờ dữ liệu nến ngày VN-INDEX từ vnstock...")

with t2:
    if not d_board.empty:
        fig_m = px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0,'#00e5ff'],[0.5,'#f5b041'],[1,'#cc00ff']], range_color=[-7, 7])
        st.plotly_chart(fig_m.update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.warning("⚠️ Chưa có dữ liệu Dòng tiền (Kiểm tra lại kết nối TCBS)")

with t3:
    if not d_board.empty:
        st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}).map(lambda v: f'color: {"#00e676" if v>0 else "#ff4d4d" if v<0 else "#f5b041"}', subset=['%']), hide_index=True, use_container_width=True)
    else: st.warning("⚠️ Bảng giá Top 100 đang được cập nhật...")

with t4:
    if not d_rep.empty:
        st.dataframe(d_rep, column_config={"Link": st.column_config.LinkColumn("Tài liệu")}, hide_index=True, use_container_width=True)
    else: st.warning("⚠️ CafeF đang chặn IP máy chủ hoặc không có báo cáo mới.")

with t5:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        score = sum([c > ma, v > v_ma, adv > dec])
        
        status_map = {3: ("RẤT TÍCH CỰC", "#cc00ff"), 2: ("TÍCH CỰC", "#00e676"), 1: ("THẬN TRỌNG", "#f5b041"), 0: ("TIÊU CỰC", "#ff4d4d")}
        txt, col = status_map[score]
        
        st.markdown(f"""
        <div class='card'>
            <h3 style='color:{col}'>{txt} ({score}/3 Điểm)</h3>
            <p><b>Giá vs MA20:</b> {'Tốt' if c > ma else 'Yếu'} | <b>Thanh khoản:</b> {'Đột biến' if v > v_ma else 'Thấp'} | <b>Cung-Cầu:</b> {adv} Tăng / {dec} Giảm</p>
            <hr style='border-color:#3f3f5a'>
            <p>👉 <b>Hành động:</b> {'Nâng tỷ trọng' if score >= 2 else 'Quản trị rủi ro'}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("🔮 Hệ thống AI cần cả dữ liệu VN-INDEX và Bảng giá để chấm điểm kịch bản.")
