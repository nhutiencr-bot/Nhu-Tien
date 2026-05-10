import streamlit as st, pandas as pd, plotly.express as px, plotly.graph_objects as go
import yfinance as yf
import requests, re

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", layout="wide")
st.markdown("""<style>div[data-testid="stMetric"], .card {background-color: #1e1e2f; padding: 15px; border-radius: 10px; color: white;} .card {border-left: 5px solid #ffaa00; margin-top: 10px;}</style>""", unsafe_allow_html=True)

C_GN, C_RD, C_RF = '#00e676', '#ff4d4d', '#f5b041'
col1, col2 = st.columns([4, 1])
col1.title("🧚‍♀️ FAIRY INVEST - Dashboard")
if col2.button("🔄 Cập nhật Dữ liệu", use_container_width=True): st.cache_data.clear()

# 2. HÀM LẤY DỮ LIỆU (Dùng Yahoo Finance + TCBS)
@st.cache_data(ttl=120)
def get_market():
    # Lấy Top 100 từ TCBS (Chỉ 1s, không tốn RAM)
    try:
        d = requests.get("https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE", headers={'User-Agent': 'Mozilla'}, timeout=5).json()['data']
        df = pd.DataFrame(d)[['ticker', 'price', 'priceChange', 'percentPriceChange', 'volume']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'KL']
        return df.sort_values('KL', ascending=False).head(100)
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_hist():
    # Lấy VN-INDEX từ Yahoo Finance (Bất tử cuối tuần/ban đêm)
    try:
        df = yf.Ticker("^VNINDEX").history(period="3mo").reset_index()
        if df.empty: return pd.DataFrame()
        df = df.rename(columns={'Date': 'time', 'Close': 'close', 'Volume': 'volume'})
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef():
    # Lấy báo cáo từ CafeF
    res = []
    try:
        html = requests.get("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", headers={"User-Agent":"Mozilla"}).text
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m = re.search(r'<a[^>]*class="doc_title"[^>]*>(.*?)</a>', b)
            l_m = re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                res.append({
                    "Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1) or "",
                    "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ",
                    "Tiêu đề": t, "Link": "https://s.cafef.vn" + l_m.group(1)
                })
    except: pass
    return pd.DataFrame(res)

# 3. HIỂN THỊ 5 TAB GIAO DIỆN
with st.spinner("Đang tải dữ liệu từ Yahoo & TCBS..."):
    df_100, df_hist, df_rep = get_market(), get_hist(), get_cafef()

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top 100", "📝 Báo cáo", "🔮 Kịch bản AI"])

with t1:
    if not df_hist.empty:
        c, p = df_hist.iloc[-1]['close'], df_hist.iloc[-2]['close']
        dt_str = df_hist.iloc[-1]['time'].strftime('%d/%m/%Y')
        st.metric(f"VN-INDEX (Chốt phiên {dt_str})", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+.2f}%)")
        fig = go.Figure([go.Scatter(x=df_hist['time'], y=df_hist['close'], name='VN-INDEX', line=dict(color='white')), go.Scatter(x=df_hist['time'], y=df_hist['MA20'], name='MA20', line=dict(color=C_GN, dash='dash'))])
        fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, use_container_width=True)

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("HOSE"), 'Mã CK'], values='KL', color='%', color_continuous_scale=[[0, '#00e5ff'], [0.5, C_RF], [1, '#cc00ff']], range_color=[-7, 7])
        fig_m.update_layout(margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_100.empty:
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'KL': '{:,.0f}'}).map(lambda v: f'color: {C_GN if v>0 else C_RD if v<0 else C_RF}', subset=['%']), hide_index=True, use_container_width=True)

with t4:
    if not df_rep.empty:
        if not df_100.empty: df_rep = pd.merge(df_rep, df_100[['Mã CK', 'Giá']], on='Mã CK', how='left')
        st.dataframe(df_rep.style.map(lambda v: f'color: {C_GN if "MUA" in str(v).upper() else C_RD if "BÁN" in str(v).upper() else C_RF}; font-weight:bold;', subset=['Khuyến nghị']).format({'Giá': '{:,.2f}'}), column_config={"Link": st.column_config.LinkColumn("Tài liệu", display_text="📥 PDF")}, hide_index=True, use_container_width=True)

with t5:
    if not df_hist.empty and not df_100.empty:
        c, ma, v, v_ma = df_hist.iloc[-1]['close'], df_hist.iloc[-1]['MA20'], df_hist.iloc[-1]['volume'], df_hist.iloc[-1]['V_MA20']
        adv, dec = len(df_100[df_100['%'] > 0]), len(df_100[df_100['%'] < 0])
        score = sum([c > ma, v > v_ma, adv > dec])
        st_col, st_txt = [C_RD, C_RF, C_GN, '#cc00ff'][score], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"][score]
        
        st.markdown(f"""
        <div class="card">
            <h3 style="color:{st_col}; margin-bottom: 5px;">{st_txt} ({score}/3 Điểm)</h3>
            <p style="margin: 5px 0;"><b>1. Giá vs MA20:</b> {'Tốt (Trên MA20)' if c > ma else 'Xấu (Dưới MA20)'} | <b>2. Dòng tiền:</b> {'Vượt' if v > v_ma else 'Dưới'} trung bình | <b>3. Cung-Cầu:</b> {adv} Tăng / {dec} Giảm</p>
            <hr style="border-color: #3f3f5a; margin: 10px 0;">
            <p style="margin: 0;">👉 <b>Hành động:</b> {'Thị trường khỏe, ưu tiên gia tăng tỷ trọng cổ phiếu.' if score >= 2 else 'Thị trường rủi ro, ưu tiên hạ tỷ trọng margin.'}</p>
        </div>
        """, unsafe_allow_html=True)
