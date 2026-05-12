import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import plotly.graph_objects as go
import requests
import urllib.parse
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%); padding: 20px; border-radius: 10px; color: white; border-left: 5px solid #00e5ff; margin-bottom: 15px; }
    .scenario-box { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & TRẠNG THÁI
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_d = now.strftime('%Y-%m-%d')
start_d_idx = (now - timedelta(days=5)).strftime('%Y-%m-%d')
start_ma = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour <= 14) or (now.hour == 15 and now.minute <= 30) or (now.hour == 8 and now.minute >= 50))
if is_trading: st.sidebar.success(f"🟢 Thị trường đang MỞ CỬA\n\nCập nhật lúc: {now.strftime('%H:%M:%S')}")
else: st.sidebar.warning(f"🔴 Thị trường ĐÃ ĐÓNG CỬA\n\nDữ liệu chốt phiên gần nhất.")

# MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. LÕI DỮ LIỆU REAL-TIME & VƯỢT TƯỜNG LỬA
# ==========================================
def fetch_proxy(target_url, is_json=True):
    encoded = urllib.parse.quote(target_url, safe='')
    urls = [target_url, f"https://api.codetabs.com/v1/proxy?quest={encoded}", f"https://api.allorigins.win/raw?url={encoded}"]
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200 and len(res.content) > 50:
                return res.json() if is_json else res.text
        except: continue
    return None

@st.cache_data(ttl=86400)
def get_sectors():
    try:
        df = listing_companies()
        return df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=30) # Cache 30 giây để đảm bảo nhảy số Real-time
def get_realtime_market():
    # Lấy Real-time từ VNDirect thay vì vnstock 1D
    data = fetch_proxy("https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=150", True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol', 'accumulatedVal']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
        df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
        
        sectors = get_sectors()
        df['Nhóm Ngành'] = df['Mã CK'].map(sectors).fillna('Khác')
        return df.dropna(subset=['Tổng KL'])
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_realtime_index():
    return stock_historical_data('VNINDEX', start_d_idx, end_d, '1', 'index')

@st.cache_data(ttl=60)
def get_index_contrib():
    data = fetch_proxy("https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30", True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['ticker', 'point']]
        df.columns = ['Mã CK', 'Điểm']
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_ma():
    try:
        df = stock_historical_data('VNINDEX', start_ma, end_d, '1D', 'index')
        if not df.empty:
            df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
            return df.dropna().reset_index(drop=True)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_cafef_reports():
    html = fetch_proxy("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", False)
    res = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m, s_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b), re.search(r'class="doc_source"[^>]*>(.*?)</span>', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                tk = (re.search(r'\b([A-Z0-9]{3})\b', t) or re.search('','')).group(0)
                act, t_up = "ĐÁNH GIÁ", t.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): act = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): act = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): act = "NẮM GIỮ"
                res.append({"Mã CK": tk, "Khuyến nghị": act, "CTCK": s_m.group(1).strip() if s_m else "", "Nội dung": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN 5 TABS HỢP NHẤT
# ==========================================
with st.spinner("Đang kết nối API lấy dữ liệu Real-time..."):
    df_market, df_idx, df_c, df_ma, df_rep = get_realtime_market(), get_realtime_index(), get_index_contrib(), get_vnindex_ma(), get_cafef_reports()

t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Tác động", "🗺️ Bản đồ Dòng tiền", "📊 Top 150 Giao Dịch", "📝 Khuyến nghị CafeF", "🤖 AI Nhận định (VSA)"])

def style_v(v):
    try:
        v = float(v)
        if v >= 6.8: return f'color: {C_CEIL}; font-weight: bold;'
        elif v <= -6.8: return f'color: {C_FLOOR}; font-weight: bold;'
        elif v > 0: return f'color: {C_GREEN}; font-weight: bold;'
        elif v == 0: return f'color: {C_REF}; font-weight: bold;'
        elif v > -3: return f'color: {C_RED}; font-weight: bold;'
        else: return f'color: {C_DRED}; font-weight: bold;'
    except: return ''

# TAB 1: VN-INDEX
with t1:
    if not df_idx.empty:
        df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
        dates = df_idx['date'].unique()
        if len(dates) >= 2:
            dt_t, dt_y = df_idx[df_idx['date'] == dates[-1]].copy(), df_idx[df_idx['date'] == dates[-2]].copy()
            c, t, p = dt_t.iloc[-1]['close'], dt_t.iloc[-1]['time'], dt_y.iloc[-1]['close']
            st.metric(f"VN-INDEX (Lúc: {t})", f"{c:,.2f}", f"{c-p:+,.2f} điểm ({(c-p)/p*100:+,.2f}%)")
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🌊 Biểu đồ Thanh khoản (Hôm nay vs Hôm qua)")
                dt_t['ts'], dt_y['ts'] = pd.to_datetime(dt_t['time']).dt.strftime('%H:%M'), pd.to_datetime(dt_y['time']).dt.strftime('%H:%M')
                dt_t['cum'], dt_y['cum'] = dt_t['volume'].cumsum(), dt_y['volume'].cumsum()
                fig_liq = go.Figure()
                fig_liq.add_trace(go.Scatter(x=dt_y['ts'], y=dt_y['cum'], fill='tozeroy', name='Hôm qua', line=dict(color='rgba(65, 105, 225, 0.6)')))
                fig_liq.add_trace(go.Scatter(x=dt_t['ts'], y=dt_t['cum'], fill='tozeroy', name='Hôm nay', line=dict(color='rgba(154, 205, 50, 0.9)')))
                st.plotly_chart(fig_liq.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350, legend=dict(orientation="h", y=1.02, x=1)), use_container_width=True)

            with c2:
                st.markdown("#### 🎯 Top Cổ Phiếu Tác Động VN-INDEX")
                if not df_c.empty:
                    res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                    fig_b = go.Figure(go.Bar(x=res['Mã CK'], y=res['Điểm'], marker_color=[C_GREEN if v > 0 else C_RED for v in res['Điểm']], text=res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                    st.plotly_chart(fig_b.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350), use_container_width=True)

# TAB 2: BẢN ĐỒ NHIỆT
with t2:
    if not df_market.empty:
        fig = px.treemap(df_market, path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], values='Tổng GT', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7], custom_data=['%', 'Tổng KL'])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", textposition="middle center", textfont=dict(color="white", size=13))
        st.plotly_chart(fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=650), use_container_width=True)

# TAB 3: BẢNG GIÁ
with t3:
    if not df_market.empty:
        st.markdown("### 📊 Top 150 Cổ Phiếu Giao Dịch Mạnh Nhất Toàn Thị Trường")
        st.dataframe(df_market.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}', 'Tổng GT': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

# TAB 4: KHUYẾN NGHỊ
with t4:
    if not df_rep.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị Phân Tích")
        st.dataframe(df_rep.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Bấm xem PDF")}, hide_index=True, use_container_width=True, height=600)

# TAB 5: AI VSA
with t5:
    if not df_ma.empty and not df_market.empty and not df_idx.empty:
        c, ma = df_idx.iloc[-1]['close'], df_ma.iloc[-1]['MA20']
        
        # Tính khối lượng hôm nay so với MA20
        dt_last = df_idx['date'].unique()[-1]
        v = df_idx[df_idx['date'] == dt_last]['volume'].sum()
        vma = df_ma.iloc[-1]['V_MA20']
        
        adv, dec = len(df_market[df_market['%'] > 0]), len(df_market[df_market['%'] < 0])
        
        v_mil, vma_mil = v / 1e6, vma / 1e6
        
        if v > vma:
            if c > ma: vol_msg, kl_col = f"Dòng tiền <b style='color:#00e676;'>MUA CHỦ ĐỘNG</b> mạnh (Đạt {v_mil:,.1f} Tr CP, vượt mức TB {vma_mil:,.1f} Tr CP).", C_GREEN
            else: vol_msg, kl_col = f"Áp lực <b style='color:#ff4d4d;'>BÁN THÁO</b> lớn (Đạt {v_mil:,.1f} Tr CP, vượt mức TB {vma_mil:,.1f} Tr CP).", C_RED
        else:
            if c > ma: vol_msg, kl_col = f"Thanh khoản <b style='color:#f5b041;'>THẤP</b> (Chỉ đạt {v_mil:,.1f} Tr CP, dưới mức TB {vma_mil:,.1f} Tr CP). Cầu dè dặt.", C_REF
            else: vol_msg, kl_col = f"Thanh khoản <b style='color:#ff4d4d;'>SUY YẾU</b> (Đạt {v_mil:,.1f} Tr CP, dưới mức TB {vma_mil:,.1f} Tr CP). Dòng tiền vắng bóng.", C_RED

        if adv > dec * 1.5: rong_msg, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm). Sắc xanh áp đảo.", C_GREEN
        elif dec > adv * 1.5: rong_msg, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm). Dấu hiệu 'Xanh vỏ đỏ lòng'.", C_RED
        else: rong_msg, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Luân chuyển dòng tiền.", C_REF

        st.markdown(f"""
        <div class='card'>
            <h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TRẠNG THÁI (REAL-TIME)</h2>
            <ul style='font-size: 17px; line-height: 1.8;'>
                <li><b>Động lượng Khối lượng:</b> {vol_msg}</li>
                <li><b>Độ rộng thị trường (Rổ 150 mã):</b> <b style='color:{rong_col}'>{rong_msg}</b></li>
                <li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{"#00e676" if c > ma else "#ff4d4d"}'>{'NẰM TRÊN' if c > ma else 'RƠI XUỐNG DƯỚI'}</b> MA20 ({ma:,.2f}).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        score = sum([c > ma, v > vma, adv > dec])
        if score >= 2: sc_col, sc_ti, sc_de = C_GREEN, "🟢 Kịch Bản Tích Cực", "Sự lan tỏa diễn ra tốt. Ưu tiên nắm giữ, gia tăng tỷ trọng và mở mua mới mã có nền giá."
        elif score == 1: sc_col, sc_ti, sc_de = C_REF, "🟡 Kịch Bản Đi Ngang", "Trạng thái phân hóa mạnh, có kéo trụ. Duy trì tỷ trọng 50/50, mua bán chọn lọc, không FOMO."
        else: sc_col, sc_ti, sc_de = C_RED, "🔴 Kịch Bản Rủi Ro", "Áp lực bán lớn, mất hỗ trợ. Quản trị rủi ro tuyệt đối, kiên quyết hạ Margin và đứng ngoài."

        st.markdown(f"<div class='scenario-box' style='border-left: 5px solid {sc_col};'><h3 style='color:{sc_col}; margin-top:0;'>{sc_ti}</h3><p style='font-size:16px;'>{sc_de}</p></div>", unsafe_allow_html=True)

if is_trading:
    time.sleep(60)
    st.rerun()
