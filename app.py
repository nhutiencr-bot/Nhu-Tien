import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
import yfinance as yf, requests, re

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("<style>div[data-testid='stMetric'], .card {background: #1e1e2f; padding: 15px; border-radius: 10px; color: white;} .card{border-left:5px solid #ffaa00; margin-top:10px;}</style>", unsafe_allow_html=True)

col1, col2 = st.columns([4, 1])
col1.title("🧚‍♀️ FAIRY INVEST")
if col2.button("🔄 Làm mới hệ thống"):
    st.cache_data.clear()
    st.rerun()

# 2. HÀM TẠO DỮ LIỆU DỰ PHÒNG (FIX LỖI LENGTH TRIỆT ĐỂ)
def get_mock_100():
    return pd.DataFrame({'Mã CK':['FPT','HPG','SSI'], 'Giá':[135,29,36], '+/-':[1.0,0.5,-0.5], '%':[1.5,1.0,-1.0], 'KL':[1000000,2000000,1500000]})

def get_mock_idx():
    # Khai báo list trực tiếp để chiều dài luôn là 5, không bao giờ lệch
    data = {
        'time': pd.to_datetime(['2026-05-06', '2026-05-07', '2026-05-08', '2026-05-09', '2026-05-10']),
        'close': [1240.0, 1245.0, 1250.0, 1248.0, 1252.0],
        'volume': [500000000] * 5,
        'MA20': [1245.0] * 5,
        'V_MA20': [500000000.0] * 5
    }
    return pd.DataFrame(data)

# 3. LẤY DỮ LIỆU
@st.cache_data(ttl=120)
def get_tcbs():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        d = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=5).json()['data']
        df = pd.DataFrame(d)[['ticker','price','priceChange','percentPriceChange','volume']].rename(columns={'ticker':'Mã CK','price':'Giá','priceChange':'+/-','percentPriceChange':'%','volume':'KL'})
        return df.sort_values('KL', ascending=False).head(100), False
    except: return get_mock_100(), True

@st.cache_data(ttl=300)
def get_yf():
    try:
        df = yf.Ticker("^VNINDEX").history(period="2mo").reset_index().rename(columns={'Date':'time','Close':'close','Volume':'volume'})
        if df.empty or len(df) < 20: return get_mock_idx(), True
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True), False
    except: return get_mock_idx(), True

@st.cache_data(ttl=3600)
def get_cafef():
    res = []
    try:
        h = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=20", headers={"User-Agent":"Mozilla/5.0"}, timeout=10).text
        for b in re.findall(r'<li.*?>(.*?)</li>', h, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res.append({"Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1), "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ", "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
    except: pass
    return pd.DataFrame(res)

# 4. HIỂN THỊ
d_100, err1 = get_tcbs()
d_idx, err2 = get_yf()
d_rep = get_cafef()

if err1 or err2: st.error("⚠️ Kết nối bị hạn chế. Đang hiển thị dữ liệu dự phòng.")

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 AI What-if"])

with t1:
    if not d_idx.empty:
        c, p = d_idx.iloc[-1]['close'], d_idx.iloc[-2]['close']
        st.metric("VN-INDEX", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=d_idx['time'], y=d_idx['close'], name='VNINDEX'), go.Scatter(x=d_idx['time'], y=d_idx['MA20'], name='MA20', line=dict(dash='dash'))])
        st.plotly_chart(fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white'), use_container_width=True)

with t2:
    if not d_100.empty: st.plotly_chart(px.treemap(d_100, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale='RdYlGn', range_color=[-7, 7]).update_layout(margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

with t3:
    if not d_100.empty: st.dataframe(d_100.style.format({'Giá':'{:,.2f}','%':'{:+,.2f}%','KL':'{:,.0f}'}), hide_index=True, use_container_width=True)

with t4:
    if not d_rep.empty: st.dataframe(d_rep, column_config={"Link": st.column_config.LinkColumn("Tải về")}, hide_index=True, use_container_width=True)

with t5:
    if not d_idx.empty and not d_100.empty:
        c, ma, v, v_ma = d_idx.iloc[-1]['close'], d_idx.iloc[-1]['MA20'], d_idx.iloc[-1]['volume'], d_idx.iloc[-1]['V_MA20']
        adv, dec = len(d_100[d_100['%'] > 0]), len(d_100[d_100['%'] < 0])
        sc = sum([c > ma, v > v_ma, adv > dec])
        col, txt = ['#ff4d4d', '#f5b041', '#00e676', '#cc00ff'][sc], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][sc]
        st.markdown(f"<div class='card'><h3 style='color:{col}'>{txt} ({sc}/3)</h3><p>Giá {'trên' if c>ma else 'dưới'} MA20 | KL {'vượt' if v>v_ma else 'dưới'} TB | Tăng:{adv}/Giảm:{dec}</p></div>", unsafe_allow_html=True)
