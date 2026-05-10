import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
import yfinance as yf, requests, re

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>div[data-testid='stMetric'], .card {background: #1e1e2f; padding: 15px; border-radius: 10px; color: white;} .card{border-left:5px solid #ffaa00; margin-top:10px;}</style>", unsafe_allow_html=True)

c1, c2 = st.columns([4, 1])
c1.title("🧚‍♀️ FAIRY INVEST")
if c2.button("🔄 Cập nhật Web"): st.cache_data.clear()

# 2. LẤY DỮ LIỆU (YAHOO + TCBS + CAFEF)
@st.cache_data(ttl=120)
def get_tcbs():
    try:
        d = requests.get("https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE", headers={'User-Agent': 'Mozilla'}, timeout=5).json()['data']
        return pd.DataFrame(d)[['ticker', 'price', 'priceChange', 'percentPriceChange', 'volume']].rename(columns={'ticker':'Mã CK', 'price':'Giá', 'priceChange':'+/-', 'percentPriceChange':'%', 'volume':'KL'}).sort_values('KL', ascending=False).head(100)
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_yf():
    try:
        df = yf.Ticker("^VNINDEX").history(period="2mo").reset_index().rename(columns={'Date':'time', 'Close':'close', 'Volume':'volume'})
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef():
    res = []
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", headers={"User-Agent":"Mozilla"}).text
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'<a[^>]*class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res.append({"Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1), "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
    except: pass
    return pd.DataFrame(res)

# 3. HIỂN THỊ
with st.spinner("Đang tải dữ liệu..."):
    d_100, d_idx, d_rep = get_tcbs(), get_yf(), get_cafef()

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p, dt = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close'], d_idx.iloc[-1]['time'].strftime('%d/%m/%Y')
        st.metric(f"VN-INDEX ({dt})", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        st.plotly_chart(go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash', color='#00e676'))]).update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t2:
    if not d_100.empty: st.plotly_chart(px.treemap(d_100, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0, '#00e5ff'], [0.5, '#f5b041'], [1, '#cc00ff']], range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t3:
    if not d_100.empty: st.dataframe(d_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'KL': '{:,.0f}'}).map(lambda v: f'color: {"#00e676" if v>0 else "#ff4d4d" if v<0 else "#f5b041"}', subset=['%']), hide_index=True, use_container_width=True)

with t4:
    if not d_rep.empty:
        if not d_100.empty: d_rep = pd.merge(d_rep, d_100[['Mã CK', 'Giá']], on='Mã CK', how='left')
        st.dataframe(d_rep.style.map(lambda v: f'color: {"#00e676" if "MUA" in str(v).upper() else "#ff4d4d" if "BÁN" in str(v).upper() else "#f5b041"}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Tải về")}, hide_index=True, use_container_width=True)

with t5:
    if not d_idx.empty and not d_100.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_100[d_100['%'] > 0]), len(d_100[d_100['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3 Điểm)</h3><p><b>1. Giá vs MA20:</b> {'Tốt' if c>ma else 'Xấu'} | <b>2. Thanh khoản:</b> {'Vượt' if v>v_ma else 'Dưới'} TB | <b>3. Cung-Cầu:</b> {adv} Tăng / {dec} Giảm</p><hr><p>👉 <b>Chiến lược:</b> {'Gia tăng tỷ trọng' if sc>=2 else 'Quản trị rủi ro'}</p></div>", unsafe_allow_html=True)
