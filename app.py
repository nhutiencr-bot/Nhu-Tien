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
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

c1, c2 = st.columns([4, 1])
c1.title(f"🧚‍♀️ FAIRY INVEST - {now.strftime('%d/%m/%Y')}")
if c2.button("🔄 Cập nhật Live", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 2. HÀM LẤY DỮ LIỆU (VNSTOCK + TCBS + CAFEF)
@st.cache_data(ttl=60)
def get_data():
    df_idx, df_board, df_rep = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # 1. Lấy Chỉ số (vnstock)
    try:
        df_idx = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df_idx.empty:
            df_idx['MA20'] = df_idx['close'].rolling(20).mean()
            df_idx['V_MA20'] = df_idx['volume'].rolling(20).mean()
            df_idx = df_idx.dropna().reset_index(drop=True)
    except: pass

    # 2. Lấy Top 100 (TCBS)
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        d = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()['data']
        df_board = pd.DataFrame(d)[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'}).sort_values('KL', ascending=False).head(100)
    except: pass

    # 3. Lấy Báo cáo (CafeF)
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=20", headers={"User-Agent":"Mozilla/5.0"}, timeout=5).text
        res = []
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res.append({"Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1), "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
        df_rep = pd.DataFrame(res)
    except: pass

    return df_idx, df_board, df_rep

# 3. NẠP DỮ LIỆU
with st.spinner("Đang tải dữ liệu Real-time (vnstock)..."):
    d_idx, d_board, d_rep = get_data()

# Cảnh báo nổi bật nếu đầu phiên chưa có dữ liệu
if d_idx.empty or d_board.empty:
    st.warning("⏳ Dữ liệu tạm thời trống. Nguyên nhân: Có thể do mới mở cửa phiên sáng (hệ thống API chưa đẩy dữ liệu nến ngày) hoặc Tường lửa đang chặn. Vui lòng bấm 'Cập nhật Live' sau ít phút.")

# 4. HIỂN THỊ CÁC TAB
t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.info("Không có dữ liệu VN-INDEX lúc này.")

with t2:
    if not d_board.empty: st.plotly_chart(px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0,'#00e5ff'],[0.5,'#f5b041'],[1,'#cc00ff']], range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.info("Không có dữ liệu Bản đồ dòng tiền lúc này.")

with t3:
    if not d_board.empty: st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}).map(lambda v: f'color: {"#00e676" if v>0 else "#ff4d4d" if v<0 else "#f5b041"}', subset=['%']), hide_index=True, use_container_width=True)
    else: st.info("Không có dữ liệu Top 100 lúc này.")

with t4:
    if not d_rep.empty: st.dataframe(d_rep.style.map(lambda v: f'color: {"#00e676" if "MUA" in str(v).upper() else "#ff4d4d" if "BÁN" in str(v).upper() else "#f5b041"}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Tải về")}, hide_index=True, use_container_width=True)
    else: st.info("Không tải được Báo cáo CafeF lúc này.")

with t5:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3 Điểm)</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'dưới'} TB | Tăng:{adv}/Giảm:{dec}</p><hr><p>👉 <b>Hành động:</b> {'Gia tăng tỷ trọng' if sc>=2 else 'Quản trị rủi ro'}</p></div>", unsafe_allow_html=True)
    else: st.info("Thiếu dữ liệu để hệ thống AI đánh giá kịch bản.")
