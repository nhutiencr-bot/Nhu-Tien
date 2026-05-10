import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
    .prob-badge { background-color: #33334d; padding: 3px 8px; border-radius: 5px; font-weight: bold; color: #ffaa00; }
</style>
""", unsafe_allow_html=True)

# Khởi tạo Session State cho Menu Tab 5
if 'menu_tab5' not in st.session_state:
    st.session_state.menu_tab5 = 'Chiến lược Giao dịch'

vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_stock = (now - timedelta(days=7)).strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading:
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else:
        st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# CÁC HÀM LẤY DỮ LIỆU THỊ TRƯỜNG
# ==========================================
@st.cache_data(ttl=86400)
def get_hose_tickers():
    try:
        df = listing_companies()
        return df[df['comGroupCode'] == 'HOSE']['ticker'].head(150).tolist()
    except: return ['VCB', 'VHM', 'VIC', 'FPT', 'HPG', 'SSI', 'VND']

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {'Mã CK': t, 'Giá hiện tại': curr, '+/-': round(curr-prev, 2), '%': round((curr-prev)/prev*100, 2), 'Tổng KL': int(d.iloc[-1]['volume'])}
        except: return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
        res = list(exe.map(fetch, tickers))
    df = pd.DataFrame([r for r in res if r])
    return df.sort_values('Tổng KL', ascending=False).head(100) if not df.empty else df

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            d = pd.DataFrame(r.json()['data'])
            return d[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef_reports():
    reports = []
    try:
        url = "https://cafef.vn/du-lieu/phan-tich-bao-cao.chn"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', {'id': 'tblGridData'})
        if table:
            for row in table.find_all('tr')[1:20]:
                cols = row.find_all('td')
                if len(cols) >= 5:
                    title_tag = cols[3].find('a')
                    title = title_tag.text.strip() if title_tag else cols[3].text.strip()
                    reports.append({
                        "Ngày": cols[0].text.strip(), "Mã CK": cols[1].text.strip(), "CTCK": cols[2].text.strip(),
                        "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN)', title, re.I) or re.search('', '')).group(0).upper() or "ĐÁNH GIÁ",
                        "Giá mục tiêu": (re.search(r'mục tiêu.*?([\d,\.]+)', title, re.I) or re.search('', '')).group(1) or "N/A",
                        "Tiêu đề Báo cáo": title, "Link PDF": "https://cafef.vn" + title_tag['href'] if title_tag and title_tag.has_attr('href') else "N/A"
                    })
    except: pass
    return pd.DataFrame(reports)

# Lấy dữ liệu VNINDEX dài hạn cho Tab 5
@st.cache_data(ttl=300)
def get_vnindex_history():
    try:
        start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['Vol_MA20'] = df['volume'].rolling(window=20).mean()
        return df
    except: return pd.DataFrame()

# ==========================================
# HIỂN THỊ GIAO DIỆN
# ==========================================
df_100 = get_market_data()
t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Khuyến Nghị CTCK", "🔮 Kịch bản Thị trường"])

# --- TAB 1, 2, 3, 4 (RÚT GỌN ĐỂ TẬP TRUNG TAB 5) ---
with t1:
    try:
        df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
        cur, ref = df_daily.iloc[-1]['close'], df_daily.iloc[-2]['close']
        st.metric(f"Điểm số VN-INDEX", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌊 Thanh khoản")
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                dates = pd.to_datetime(df_idx['time']).dt.date.unique()
                df_t = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-1]].copy()
                df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                fig = go.Figure()
                if len(dates) >= 2:
                    df_y = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-2]].copy()
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Phiên trước', line=dict(color='rgba(150,150,150,0.5)')))
                fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Hôm nay', line=dict(color=C_GREEN)))
                fig.update_layout(height=380, margin=dict(l=0,r=0,t=0,b=0), legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### 🎯 Tác động tới VN-INDEX")
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=[C_GREEN if v>0 else C_RED for v in df_res['Điểm']], text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig_b, use_container_width=True)
    except: st.info("Hệ thống biểu đồ đang tải...")

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_100.empty:
        def style_v(v): return f'color: {C_CEIL if v>=6.8 else C_FLOOR if v<=-6.8 else C_GREEN if v>0 else C_RED if v<0 else C_REF}; font-weight: bold;'
        st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True)

with t4:
    st.markdown("### 📝 Tổng hợp Báo Cáo Phân Tích (CafeF)")
    df_rep = get_cafef_reports()
    if not df_rep.empty and not df_100.empty:
        df_rep = pd.merge(df_rep, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')[['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']]
        def s_act(val): return f'color: {C_GREEN if "MUA" in str(val) or "KHẢ" in str(val) else C_RED if "BÁN" in str(val) else C_REF}; font-weight: bold;'
        st.dataframe(df_rep.style.map(s_act, subset=['Khuyến nghị']).format({'Giá hiện tại': '{:,.2f}'}), column_config={"Link PDF": st.column_config.LinkColumn("Tài liệu")}, use_container_width=True)


# ==========================================
# TAB 5: KỊCH BẢN THỊ TRƯỜNG (CÓ TƯƠNG TÁC)
# ==========================================
with t5:
    col_content, col_menu = st.columns([7, 3])
    df_hist = get_vnindex_history()
    
    # -- CỘT MENU BÊN PHẢI (CÁC NÚT BẤM STREAMLIT NATIVE) --
    with col_menu:
        st.markdown("<h4 style='color: white;'>📑 Menu Phân Tích</h4>", unsafe_allow_html=True)
        # Sử dụng Radio button nhưng ẩn label để giả làm menu điều hướng
        selected_menu = st.radio(
            "Chọn chức năng:",
            ["🔮 Chiến lược Giao dịch", "📈 Xu hướng Giá", "📊 Xu hướng Khối lượng", "⚖️ Cung - Cầu"],
            label_visibility="collapsed"
        )
        st.session_state.menu_tab5 = selected_menu

    # -- CỘT NỘI DUNG BÊN TRÁI --
    with col_content:
        if df_hist.empty:
            st.warning("Đang tải dữ liệu phân tích...")
        else:
            # Lấy thông số Real-time để làm Kịch bản Dynamic
            current_close = df_hist.iloc[-1]['close']
            ma20 = df_hist.iloc[-1]['MA20']
            vol_today = df_hist.iloc[-1]['volume']
            vol_ma20 = df_hist.iloc[-1]['Vol_MA20']
            
            # Tính toán xu hướng
            is_uptrend = current_close > ma20
            trend_text = "TÍCH CỰC" if is_uptrend else "TIÊU CỰC"
            trend_color = C_GREEN if is_uptrend else C_RED
            
            # 1. Nếu chọn Chiến lược giao dịch (What-if)
            if st.session_state.menu_tab5 == "🔮 Chiến lược Giao dịch":
                # Thuật toán tự động đẩy xác suất dựa trên đường MA20
                prob_up = "55 - 65%" if is_uptrend else "15 - 25%"
                prob_down = "15 - 25%" if is_uptrend else "55 - 65%"
                
                html_content = f"""
                <div class="scenario-card">
                    <div class="scenario-title">Dự báo & Chiến lược Giao dịch (Dynamic)</div>
                    <p>Hệ thống đánh giá xu hướng ngắn hạn hiện tại đang: <b style='color:{trend_color}'>{trend_text}</b> (VN-INDEX = {current_close:,.2f} so với MA20 = {ma20:,.2f}).</p>
                    <hr style="border-color: #3f3f5a;">
                    
                    <div class="scenario-item">
                        <p>🟢 <b>Kịch bản Tích cực</b> (Tiếp diễn đà tăng) - Xác suất <span class="prob-badge">{prob_up}</span></p>
                        <p>Giá giữ vững trên mốc MA20 ({ma20:,.0f}), dòng tiền lan tỏa sang Midcap.</p>
                        <p><b>Hành động:</b> Gia tăng tỷ trọng cổ phiếu, nắm giữ các mã đang hút tiền.</p>
                    </div>
                    
                    <hr style="border-color: #3f3f5a;">
                    <div class="scenario-item">
                        <p>🟡 <b>Kịch bản Trung tính</b> (Sideway tích lũy) - Xác suất <span class="prob-badge">20 - 30%</span></p>
                        <p>Giá dao động đi ngang quanh trục {current_close:,.0f} biên độ hẹp, thanh khoản thấp.</p>
                        <p><b>Hành động:</b> Duy trì tỷ trọng 50% Cổ phiếu / 50% Tiền mặt, giao dịch biên (Mua hỗ trợ, Bán kháng cự).</p>
                    </div>
                    
                    <hr style="border-color: #3f3f5a;">
                    <div class="scenario-item">
                        <p>🔴 <b>Kịch bản Tiêu cực</b> (Phá vỡ hỗ trợ) - Xác suất <span class="prob-badge">{prob_down}</span></p>
                        <p>Đánh mất mốc {ma20:,.0f} với khối lượng lớn, áp lực bán lan rộng toàn thị trường.</p>
                        <p><b>Hành động:</b> Hạ tỷ trọng margin ngay lập tức, đưa tài khoản về thế phòng thủ.</p>
                    </div>
                </div>
                """
                st.markdown(html_content, unsafe_allow_html=True)

            # 2. Nếu chọn Xu hướng Giá
            elif st.session_state.menu_tab5 == "📈 Xu hướng Giá":
                st.markdown(f"### Phân tích Xu hướng Giá VN-INDEX")
                st.info(f"VN-INDEX hiện tại đang ở mức **{current_close:,.2f}**, {'NẰM TRÊN' if is_uptrend else 'NẰM DƯỚI'} đường trung bình 20 ngày (MA20: {ma20:,.2f}).")
                
                # Vẽ biểu đồ Line chart có MA20
                fig_price = go.Figure()
                fig_price.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['close'], name='VN-INDEX', line=dict(color='white', width=2)))
                fig_price.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['MA20'], name='MA20', line=dict(color=C_GREEN, width=1, dash='dash')))
                fig_price.update_layout(height=400, plot_bgcolor='#1e1e2f', paper_bgcolor='#1e1e2f', font_color='white')
                st.plotly_chart(fig_price, use_container_width=True)

            # 3. Nếu chọn Xu hướng Khối lượng
            elif st.session_state.menu_tab5 == "📊 Xu hướng Khối lượng":
                vol_status = "VƯỢT" if vol_today > vol_ma20 else "THẤP HƠN"
                st.markdown(f"### Phân tích Khối lượng Giao dịch")
                st.info(f"Khối lượng phiên gần nhất đạt **{vol_today:,.0f}** cổ phiếu, {vol_status} mức trung bình 20 phiên ({vol_ma20:,.0f}).")
                
                # Vẽ Bar chart khối lượng
                b_colors = [C_GREEN if df_hist['close'].iloc[i] > df_hist['close'].iloc[i-1] else C_RED for i in range(len(df_hist))]
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Bar(x=df_hist['time'], y=df_hist['volume'], name='Khối lượng', marker_color=b_colors))
                fig_vol.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['Vol_MA20'], name='Trung bình 20 phiên', line=dict(color='#ffaa00', width=2)))
                fig_vol.update_layout(height=400, plot_bgcolor='#1e1e2f', paper_bgcolor='#1e1e2f', font_color='white')
                st.plotly_chart(fig_vol, use_container_width=True)
                
            # 4. Nếu chọn Cung Cầu
            elif st.session_state.menu_tab5 == "⚖️ Cung - Cầu":
                st.markdown(f"### Đánh giá Cung - Cầu Thị trường")
                advances = len(df_100[df_100['%'] > 0])
                declines = len(df_100[df_100['%'] < 0])
                st.markdown(f"""
                <div class="scenario-card" style="text-align: center;">
                    <h4>Độ rộng thị trường (Trong rổ Top 100)</h4>
                    <h2 style='color: {C_GREEN}; display: inline;'>{advances} Tăng</h2>
                    <h2 style='color: gray; display: inline;'> | </h2>
                    <h2 style='color: {C_RED}; display: inline;'>{declines} Giảm</h2>
                    <p style="margin-top: 15px;">Dòng tiền đang tập trung {'kéo thị trường đi lên' if advances > declines else 'chốt lời/thoát hàng'} rõ rệt trong nhóm cổ phiếu vốn hóa lớn và thanh khoản cao.</p>
                </div>
                """, unsafe_allow_html=True)
