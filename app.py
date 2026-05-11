import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .scenario-box { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & HEADER
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Chiến Lược Toàn Thị Trường")
with col_status:
    if is_trading: st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật Live", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_LRED, C_FLOOR = '#b30000', '#ff4d4d', '#00e5ff'

# BẢNG PHÂN MÀU CỨNG NGẮC (HARD-STOPS) THEO ĐÚNG YÊU CẦU CỦA BẠN
# Dải nội suy quy đổi từ -7 đến 7 (Tổng 14 đơn vị)
MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR],            # Sàn: <= -6.8%
    [0.014, C_RED], [0.2857, C_RED],             # Đỏ Đậm: <-3.0%
    [0.2857, C_LRED], [0.4992, C_LRED],          # Đỏ Nhạt: < 0% và >= -3.0%
    [0.4992, C_REF], [0.5007, C_REF],            # Vàng: Đúng 0%
    [0.5007, C_GREEN], [0.9857, C_GREEN],        # Xanh: > 0% và < 6.8%
    [0.9857, C_CEIL], [1.0, C_CEIL]              # Tím: >= 6.8%
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}

# ==========================================
# 3. HÀM CÀO DỮ LIỆU TỪ LÕI SSI IBOARD (CHUẨN XÁC TỪNG TÍCH TẮC)
# ==========================================
@st.cache_data(ttl=30) # Lưu cache 30s để đảm bảo Real-time
def fetch_realtime_ssi():
    try:
        # Cào thẳng 3 sàn từ SSI
        res_hose = requests.get("https://iboard-query.ssi.com.vn/v2/stock/exchange/hose", headers=HEADERS, timeout=5).json()
        res_hnx = requests.get("https://iboard-query.ssi.com.vn/v2/stock/exchange/hnx", headers=HEADERS, timeout=5).json()
        res_upcom = requests.get("https://iboard-query.ssi.com.vn/v2/stock/exchange/upcom", headers=HEADERS, timeout=5).json()
        
        data = res_hose.get('data', []) + res_hnx.get('data', []) + res_upcom.get('data', [])
        df = pd.DataFrame(data)
        
        df = df[['stockSymbol', 'matchedPrice', 'priceChange', 'priceChangePercent', 'nmTotalTradedQty']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
        df[['Giá', '+/-', '%', 'Tổng KL']] = df[['Giá', '+/-', '%', 'Tổng KL']].apply(pd.to_numeric, errors='coerce')
        
        # SSI thường nhân giá với 1000, ta chia lại cho chuẩn
        if df['Giá'].max() > 1000:
            df['Giá'] = df['Giá'] / 1000
            df['+/-'] = df['+/-'] / 1000
            
        df = df.dropna(subset=['Tổng KL'])
        return df.sort_values('Tổng KL', ascending=False).head(100) # Lấy đúng 100 mã thanh khoản khủng nhất
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        # Lấy trọng số đóng góp Index từ VNDirect (Nguồn này vẫn ổn định nhất cho trọng số)
        url = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=50"
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        df = pd.DataFrame(res['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'] = df['close'].rolling(20).mean()
        df['V_MA20'] = df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_vnexpress_news():
    res = []
    try:
        xml_data = requests.get("https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss", timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:20]:
            title = item.find('title').text
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            
            action = "TIN TỨC"
            t_lower = title.lower()
            if any(kw in t_lower for kw in ["tăng", "lãi", "hút tiền", "vượt"]): action = "TÍCH CỰC"
            elif any(kw in t_lower for kw in ["giảm", "lỗ", "bán tháo", "lao dốc"]): action = "TIÊU CỰC"
                
            res.append({"Ngày": pubDate[5:16], "Phân loại": action, "Tiêu đề Báo cáo": title, "Link": link})
    except: pass
    return pd.DataFrame(res, columns=["Ngày", "Phân loại", "Tiêu đề Báo cáo", "Link"])

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang chọc thẳng vào kho dữ liệu của SSI iBoard..."):
    df_100 = fetch_realtime_ssi()
    df_gainers = df_100.sort_values('%', ascending=False).head(10) if not df_100.empty else pd.DataFrame()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_vnexpress_news()

t1, t2, t3, t4, t5, t6 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ Dòng tiền", 
    "📊 Top 100 Thanh Khoản", 
    "🚀 Top 10 Tăng Mạnh", 
    "📝 Tin Chứng khoán", 
    "🔮 AI Kịch Bản"
])

def style_v(v):
    try:
        v = float(v)
        if v >= 6.8: c = C_CEIL
        elif v <= -6.8: c = C_FLOOR
        elif v > 0: c = C_GREEN
        elif v == 0: c = C_REF
        elif v > -3: c = C_LRED
        else: c = C_RED
        return f'color: {c}; font-weight: bold;'
    except: return ''

# TAB 1: CHỈ SỐ & ĐÓNG GÓP TỶ TRỌNG
with t1:
    with st.spinner("Đang vẽ biểu đồ VN-INDEX..."):
        try:
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                df_y = df_idx[df_idx['date'] == dates[-2]].copy() if len(dates) > 1 else df_t
                    
                cur, ref = df_t.iloc[-1]['close'], df_y.iloc[-1]['close']
                st.metric(f"Điểm số VN-INDEX (Lúc {df_t.iloc[-1]['time']})", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🌊 Thanh khoản (Hôm nay vs Hôm qua)")
                    df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    
                    fig = go.Figure()
                    if len(dates) > 1: fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Hôm qua', line=dict(color='rgba(150,150,150,0.5)')))
                    fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Hôm nay', line=dict(color=C_GREEN)))
                    fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h", y=1.1), plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown("#### 🎯 Tác động điểm số tới VN-INDEX")
                    df_c = get_index_contrib()
                    if not df_c.empty:
                        df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                        b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                        fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_b, use_container_width=True)
        except: st.error("Đang cập nhật biểu đồ...")

# TAB 2: BẢN ĐỒ DÒNG TIỀN (CHIA MÀU CHUẨN XÁC)
with t2:
    if not df_100.empty:
        fig_m = px.treemap(
            df_100, path=[px.Constant("Toàn Thị Trường"), 'Mã CK'], 
            values='Tổng KL', color='%', 
            color_continuous_scale=MAP_COLORS, range_color=[-7, 7]
        )
        # Thiết lập Text hiện đúng 2 số thập phân (+6.18%) như yêu cầu
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: st.warning("Đang tải dữ liệu dòng tiền...")

# TAB 3: BẢNG GIÁ TOP 100
with t3:
    if not df_100.empty:
        st.markdown("### 📊 Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất (Real-time)")
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

# TAB 4: TOP 10 TĂNG MẠNH NHẤT
with t4:
    if not df_gainers.empty:
        st.markdown("### 🚀 Top 10 Cổ Phiếu Tăng Mạnh Nhất")
        st.dataframe(df_gainers.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=400)

# TAB 5: TIN TỨC
with t5:
    if not df_reports.empty:
        st.markdown("### 📝 Điểm Tin Thị Trường (VNExpress)")
        st.dataframe(df_reports.style.map(lambda v: f'color: {C_GREEN if "TÍCH CỰC" in str(v) else C_RED if "TIÊU CỰC" in str(v) else C_REF}; font-weight:bold;', subset=['Phân loại']), column_config={"Link": st.column_config.LinkColumn("Đọc bài")}, hide_index=True, use_container_width=True, height=600)

# TAB 6: AI KỊCH BẢN CHUYÊN SÂU
with t6:
    if not df_idx_daily.empty and not df_100.empty:
        c = float(df_idx_daily.iloc[-1]['close'])
        ma = float(df_idx_daily.iloc[-1]['MA20'])
        v = float(df_idx_daily.iloc[-1]['volume'])
        v_ma = float(df_idx_daily.iloc[-1]['V_MA20'])
        
        adv = len(df_100[df_100['%'] > 0])
        dec = len(df_100[df_100['%'] < 0])
        
        score = sum([c > ma, v > v_ma, adv > dec])
        
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
        kl_text = f"Đạt {v:,.0f} đơn vị, tương đương <b>{vol_ratio:.1f}%</b> so với đường trung bình 20 ngày (MA20 là {v_ma:,.0f})."
        if v > v_ma: kl_status = f"<span style='color:{C_GREEN}'>Dòng tiền tham gia chủ động và lan tỏa mạnh.</span>"
        else: kl_status = f"<span style='color:{C_REF}'>Lực cầu còn dè dặt, thanh khoản chưa thực sự bùng nổ.</span>"
        
        st.markdown(f"""
        <div class='card' style='background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%);'>
            <h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TÌNH TRẠNG HIỆN TẠI</h2>
            <ul style='font-size: 17px; line-height: 1.8;'>
                <li><b>Hành động Giá:</b> VN-INDEX đang ở mức <b>{c:,.2f}</b>, <span style='color:{"#00e676" if c > ma else "#ff4d4d"}'>{'nằm TRÊN' if c > ma else 'rơi XUỐNG DƯỚI'}</span> ngưỡng hỗ trợ MA20 ({ma:,.2f}).</li>
                <li><b>Động lượng Khối lượng:</b> {kl_text} {kl_status}</li>
                <li><b>Độ rộng thị trường (Top 100):</b> Phân bổ Cung/Cầu đang là <span style='color:{"#00e676" if adv > dec else "#ff4d4d"}'><b>{adv} Tăng / {dec} Giảm</b></span>.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🔮 XÂY DỰNG 3 KỊCH BẢN THỊ TRƯỜNG:")
        bg1 = "rgba(0, 230, 118, 0.15)" if score >= 2 else "rgba(255,255,255,0.05)"
        bg2 = "rgba(255, 77, 77, 0.15)" if score == 0 else "rgba(255,255,255,0.05)"
        bg3 = "rgba(245, 176, 65, 0.15)" if score == 1 else "rgba(255,255,255,0.05)"
        
        st.markdown(f"""
        <div class='scenario-box' style='background-color: {bg1}; border-left: 5px solid {C_GREEN};'>
            <h4 style='color:{C_GREEN}; margin-top:0;'>🟢 Kịch Bản 1: Bứt phá đi lên { "👈 (Khả năng cao nhất)" if score >= 2 else "" }</h4>
            <p><b>Hành động:</b> Gia tăng tỷ trọng cổ phiếu, tập trung nhóm đang hút dòng tiền trên biểu đồ heatmap. Có thể mở mua mới các mã vượt đỉnh ngắn hạn kèm thanh khoản tốt.</p>
        </div>
        <div class='scenario-box' style='background-color: {bg3}; border-left: 5px solid {C_REF};'>
            <h4 style='color:{C_REF}; margin-top:0;'>🟡 Kịch Bản 2: Đi ngang giằng co { "👈 (Khả năng cao nhất)" if score == 1 else "" }</h4>
            <p><b>Hành động:</b> Duy trì tỷ trọng cân bằng (50/50). Hạn chế mua đuổi giá xanh (FOMO). Canh chốt lời ngắn hạn ở kháng cự và mua tại vùng hỗ trợ.</p>
        </div>
        <div class='scenario-box' style='background-color: {bg2}; border-left: 5px solid {C_RED};'>
            <h4 style='color:{C_RED}; margin-top:0;'>🔴 Kịch Bản 3: Áp lực điều chỉnh { "👈 (Khả năng cao nhất)" if score == 0 else "" }</h4>
            <p><b>Hành động:</b> Quản trị rủi ro tuyệt đối. Hạ tỷ trọng Margin về 0. Đứng ngoài quan sát, chờ vùng cân bằng mới để giải ngân.</p>
        </div>
        """, unsafe_allow_html=True)
