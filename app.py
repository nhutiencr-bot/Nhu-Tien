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
# LỚP 1: CẤU HÌNH GIAO DIỆN & HỆ THỐNG
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; }
    .stTabs button p { font-size: 17px; font-weight: 600; }
    .card { background: linear-gradient(145deg, #1e1e2f, #2a2a40); padding: 20px; border-radius: 10px; color: white; border-left: 5px solid #00e5ff; margin-bottom: 15px; }
    .scenario-box { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# Thiết lập Múi giờ và Trạng thái
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
str_today = now.strftime('%Y-%m-%d')
str_5_days_ago = (now - timedelta(days=5)).strftime('%Y-%m-%d')
str_60_days_ago = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour <= 14) or (now.hour == 15 and now.minute <= 30) or (now.hour == 8 and now.minute >= 45))
if is_trading: st.sidebar.success(f"🟢 MỞ CỬA | Cập nhật: {now.strftime('%H:%M:%S')}")
else: st.sidebar.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên: {str_today}")

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

# ==========================================
# LỚP 2: LÕI XỬ LÝ DỮ LIỆU (CHỐNG CACHE TUYỆT ĐỐI)
# ==========================================
def fetch_api_busting_cache(base_url, is_json=True):
    """ Hàm này gắn thêm thời gian thực vào URL để lách bộ nhớ đệm của Proxy """
    timestamp = int(time.time())
    separator = '&' if '?' in base_url else '?'
    target_url = f"{base_url}{separator}_t={timestamp}"
    
    encoded = urllib.parse.quote(target_url, safe='')
    proxies = [target_url, f"https://api.allorigins.win/raw?url={encoded}", f"https://api.codetabs.com/v1/proxy?quest={encoded}"]
    
    for url in proxies:
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if res.status_code == 200 and len(res.content) > 50:
                return res.json() if is_json else res.text
        except: continue
    return None

@st.cache_data(ttl=86400)
def get_sectors_dict():
    """ Lấy danh sách ngành 1 lần/ngày """
    try:
        df = listing_companies()
        return df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)][['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=15) # Chỉ lưu 15 giây cho dữ liệu Real-time
def get_live_top_100():
    """ LẤY REAL-TIME: Dùng API Bảng giá trực tiếp thay vì vnstock 1D """
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=100"
    data = fetch_api_busting_cache(url, True)
    if data and 'data' in data:
        sectors = get_sectors_dict()
        res = []
        for item in data['data']:
            tk = item.get('code')
            res.append({
                'Mã CK': tk, 'Nhóm Ngành': sectors.get(tk, 'Khác'),
                'Giá': item.get('matchPrice', 0), '+/-': item.get('priceChange', 0),
                '%': item.get('changePc', 0), 'Tổng KL': item.get('accumulatedVol', 0)
            })
        return pd.DataFrame(res)
    return pd.DataFrame()

@st.cache_data(ttl=30)
def get_live_vnindex():
    """ VN-INDEX 1 phút (Intraday) """
    try: return stock_historical_data(symbol='VNINDEX', start_date=str_5_days_ago, end_date=str_today, resolution='1', type='index')
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_historical_ma20():
    """ LẤY LỊCH SỬ: Phục vụ AI tính toán xu hướng dài (MA20) """
    try:
        df = stock_historical_data('VNINDEX', str_60_days_ago, str_today, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            return df.dropna().reset_index(drop=True)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_cafef_recommendations():
    """ Quét báo cáo rải rác """
    html = fetch_api_busting_cache("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", False)
    res_list = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                title, link = t_m.group(1).strip(), "https://s.cafef.vn" + l_m.group(1)
                tk_match = re.search(r'\b([A-Z0-9]{3})\b', title)
                tk = tk_match.group(1) if tk_match else ""
                
                act, t_up = "ĐÁNH GIÁ", title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN"]): act = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): act = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): act = "NẮM GIỮ"
                res_list.append({"Mã CK": tk, "Khuyến nghị": act, "Nội dung": title, "Link": link})
    return pd.DataFrame(res_list)

# ==========================================
# LỚP 3: RENDER GIAO DIỆN (UI)
# ==========================================
with st.spinner("Đang đồng bộ dữ liệu Real-time (Đã kích hoạt chống Cache)..."):
    df_live100, df_idx, df_ma, df_rep = get_live_top_100(), get_live_vnindex(), get_historical_ma20(), get_cafef_recommendations()

t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Tác động", "🗺️ Bản đồ dòng tiền", "📊 Top 100 Active", "📝 Khuyến nghị CafeF", "🤖 AI Nhận định"])

def style_text(v):
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
            df_t, df_y = df_idx[df_idx['date'] == dates[-1]].copy(), df_idx[df_idx['date'] == dates[-2]].copy()
            c, t, p = df_t.iloc[-1]['close'], df_t.iloc[-1]['time'], df_y.iloc[-1]['close']
            
            st.metric(f"VN-INDEX (Cập nhật: {t})", f"{c:,.2f}", f"{c-p:+,.2f} điểm ({(c-p)/p*100:+,.2f}%)")
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🌊 Biểu đồ Thanh khoản")
                df_t['ts'], df_y['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M'), pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                df_t['cum'], df_y['cum'] = df_t['volume'].cumsum(), df_y['volume'].cumsum()
                
                fig_liq = go.Figure()
                fig_liq.add_trace(go.Scatter(x=df_y['ts'], y=df_y['cum'], fill='tozeroy', name='Hôm qua', line=dict(color='rgba(65, 105, 225, 0.6)')))
                fig_liq.add_trace(go.Scatter(x=df_t['ts'], y=df_t['cum'], fill='tozeroy', name='Hôm nay', line=dict(color='#00e676')))
                st.plotly_chart(fig_liq.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350, legend=dict(orientation="h", y=1.1)), use_container_width=True)

            with c2:
                st.markdown("#### 🚀 Cổ phiếu biến động mạnh")
                if not df_live100.empty:
                    df_live100['Impact'] = df_live100['%'] * df_live100['Tổng KL']
                    top_pos = df_live100[df_live100['%'] > 0].sort_values('Impact', ascending=False).head(10)
                    top_neg = df_live100[df_live100['%'] < 0].sort_values('Impact', ascending=True).head(10)
                    df_imp = pd.concat([top_neg, top_pos]).sort_values('%', ascending=True)
                    
                    fig_bar = go.Figure(go.Bar(
                        x=df_imp['%'], y=df_imp['Mã CK'], orientation='h',
                        marker_color=[C_RED if v < 0 else C_GREEN for v in df_imp['%']],
                        text=df_imp['%'].apply(lambda x: f"{x:+.2f}%"), textposition='outside'
                    ))
                    st.plotly_chart(fig_bar.update_layout(margin=dict(l=0, r=20, t=10, b=0), height=350), use_container_width=True)

# TAB 2 & 3: BẢN ĐỒ & BẢNG GIÁ
with t2:
    if not df_live100.empty:
        custom_scale = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]
        fig = px.treemap(df_live100, path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=custom_scale, range_color=[-7, 7], custom_data=['%', 'Tổng KL'])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", textfont=dict(color="white"))
        st.plotly_chart(fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=650), use_container_width=True)

with t3:
    if not df_live100.empty:
        st.dataframe(df_live100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_text, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

# TAB 4: KHUYẾN NGHỊ
with t4:
    if not df_rep.empty:
        st.dataframe(df_rep.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Xem PDF")}, hide_index=True, use_container_width=True, height=600)

# TAB 5: AI VSA
with t5:
    if not df_ma.empty and not df_live100.empty and not df_idx.empty:
        c, ma = df_idx.iloc[-1]['close'], df_ma.iloc[-1]['MA20']
        v = df_idx[df_idx['date'] == df_idx['date'].unique()[-1]]['volume'].sum()
        v_ma = df_ma.iloc[-1]['V_MA20']
        
        adv, dec = len(df_live100[df_live100['%'] > 0]), len(df_live100[df_live100['%'] < 0])
        v_mil, vma_mil = v / 1e6, v_ma / 1e6
        
        if v > v_ma: vol_msg, kl_col = (f"Dòng tiền <b style='color:{C_GREEN};'>MUA CHỦ ĐỘNG</b> mạnh", C_GREEN) if c > ma else (f"Áp lực <b style='color:{C_RED};'>BÁN THÁO</b> lớn", C_RED)
        else: vol_msg, kl_col = (f"Thanh khoản <b style='color:{C_REF};'>THẤP</b>. Cầu dè dặt", C_REF) if c > ma else (f"Thanh khoản <b style='color:{C_RED};'>SUY YẾU</b>. Cầu trống rỗng", C_RED)
        vol_msg += f" (Đạt {v_mil:,.1f} Tr CP, {'vượt' if v > v_ma else 'dưới'} TB 20 phiên {vma_mil:,.1f} Tr CP)."

        if adv > dec * 1.5: rong_msg, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm).", C_GREEN
        elif dec > adv * 1.5: rong_msg, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm).", C_RED
        else: rong_msg, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm).", C_REF

        st.markdown(f"""
        <div class='card'>
            <h3 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TRẠNG THÁI (REAL-TIME)</h3>
            <p style='font-size:16px;'>• <b>Hành động Giá:</b> VN-INDEX đang <b style='color:{C_GREEN if c > ma else C_RED}'>{'NẰM TRÊN' if c > ma else 'DƯỚI'}</b> MA20 ({ma:,.2f}).</p>
            <p style='font-size:16px;'>• <b>Khối lượng:</b> {vol_msg}</p>
            <p style='font-size:16px;'>• <b>Độ rộng thị trường:</b> <b style='color:{rong_col}'>{rong_msg}</b></p>
        </div>
        """, unsafe_allow_html=True)
        
        score = sum([c > ma, v > v_ma, adv > dec])
        if score >= 2: sc_col, sc_ti, sc_de = C_GREEN, "🟢 Kịch Bản Tích Cực", "Sự lan tỏa diễn ra tốt. Ưu tiên nắm giữ, gia tăng tỷ trọng."
        elif score == 1: sc_col, sc_ti, sc_de = C_REF, "🟡 Kịch Bản Đi Ngang", "Trạng thái phân hóa mạnh. Duy trì tỷ trọng 50/50, mua bán chọn lọc."
        else: sc_col, sc_ti, sc_de = C_RED, "🔴 Kịch Bản Rủi Ro", "Áp lực bán lớn, mất hỗ trợ. Quản trị rủi ro tuyệt đối, hạ Margin."

        st.markdown(f"<div class='scenario-box' style='border-left: 5px solid {sc_col};'><h4 style='color:{sc_col}; margin-top:0;'>{sc_ti}</h4><p>{sc_de}</p></div>", unsafe_allow_html=True)

if is_trading_hours:
    time.sleep(60)
    st.rerun()
