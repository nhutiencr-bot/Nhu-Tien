import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
from vnstock import stock_historical_data
import yfinance as yf
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
c1.title(f"🧚‍♀️ FAIRY INVEST - LIVE {now.strftime('%H:%M')}")
if c2.button("🔄 Ép lấy dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Bộ giả lập trình duyệt xịn nhất để lừa Tường lửa
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

# 2. HÀM LẤY DỮ LIỆU ĐA NGUỒN
@st.cache_data(ttl=60)
def get_data():
    df_idx, df_board, df_rep = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # 1. LẤY CHỈ SỐ (Thử vnstock -> Thất bại thì nhảy sang Yahoo)
    try:
        df_idx = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df_idx.empty:
            df_idx['MA20'], df_idx['V_MA20'] = df_idx['close'].rolling(20).mean(), df_idx['volume'].rolling(20).mean()
            df_idx = df_idx.dropna().reset_index(drop=True)
    except:
        try: # Dự phòng Yahoo Finance
            df_idx = yf.Ticker("^VNINDEX").history(period="2mo").reset_index().rename(columns={'Date':'time','Close':'close','Volume':'volume'})
            df_idx['MA20'], df_idx['V_MA20'] = df_idx['close'].rolling(20).mean(), df_idx['volume'].rolling(20).mean()
            df_idx = df_idx.dropna().reset_index(drop=True)
        except: pass

    # 2. LẤY BẢNG GIÁ TCBS (Vượt tường lửa)
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200 and 'data' in res.json():
            df_board = pd.DataFrame(res.json()['data'])[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'}).sort_values('KL', ascending=False).head(100)
    except: pass

    # 3. LẤY BÁO CÁO CAFEF (Vượt tường lửa)
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", headers=HEADERS, timeout=10).text
        res_rep = []
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res_rep.append({"Ngày": (re.search(r'class="doc_date".*?>(.*?)</span>', b) or re.search('','')).group(1) or "", "Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1) or "", "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
        df_rep = pd.DataFrame(res_rep)
    except: pass

    return df_idx, df_board, df_rep

# 3. NẠP DỮ LIỆU
with st.spinner("Đang tàng hình vượt tường lửa để lấy dữ liệu..."):
    d_idx, d_board, d_rep = get_data()

# 4. HIỂN THỊ CÁC TAB
t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        st.plotly_chart(go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))]).update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.error("Tường lửa đã chặn cả vnstock và Yahoo Finance. Vui lòng chạy code trên máy tính của bạn.")

with t2:
    if not d_board.empty: st.plotly_chart(px.treemap(d_board, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0,'#00e5ff'],[0.5,'#f5b041'],[1,'#cc00ff']], range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)
    else: st.error("TCBS đang chặn IP Mỹ của Streamlit. Vui lòng chạy code trên máy tính cá nhân.")

with t3:
    if not d_board.empty: st.dataframe(d_board.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}).map(lambda v: f'color: {"#00e676" if v>0 else "#ff4d4d" if v<0 else "#f5b041"}', subset=['%']), hide_index=True, use_container_width=True)
    else: st.error("Không lấy được dữ liệu Top 100.")

with t4:
    if not d_rep.empty: st.dataframe(d_rep.style.map(lambda v: f'color: {"#00e676" if "MUA" in str(v).upper() else "#ff4d4d" if "BÁN" in str(v).upper() else "#f5b041"}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Tải về")}, hide_index=True, use_container_width=True)
    else: st.error(f"CafeF đang chặn truy cập từ máy chủ nước ngoài. (Nguồn: {st.secrets.get('cafef_url', 'https://cafef.vn/du-lieu/phan-tich-bao-cao.chn')})")

with t5:
    if not d_idx.empty and not d_board.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_board[d_board['%'] > 0]), len(d_board[d_board['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3 Điểm)</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'dưới'} TB | Tăng:{adv}/Giảm:{dec}</p><hr><p>👉 <b>Hành động:</b> {'Gia tăng tỷ trọng' if sc>=2 else 'Quản trị rủi ro'}</p></div>", unsafe_allow_html=True)
    else: st.info("Thiếu dữ liệu để hệ thống AI đánh giá kịch bản.")
