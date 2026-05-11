import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
import urllib.parse
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist_ma = (current_time - timedelta(days=60)).strftime('%Y-%m-%d')

is_weekday = current_time.weekday() < 5
current_hour, current_minute = current_time.hour, current_time.minute
is_trading_hours = is_weekday and ((9 <= current_hour <= 14) or (current_hour == 15 and current_minute <= 30) or (current_hour == 8 and current_minute >= 50))

if is_trading_hours: st.sidebar.success(f"🟢 Thị trường đang MỞ CỬA\n\nCập nhật lúc: {current_time.strftime('%H:%M:%S')}")
else: st.sidebar.warning(f"🔴 Thị trường ĐÃ ĐÓNG CỬA\n\nDữ liệu chốt phiên ngày {end_date}")

# MÀU SẮC CHUẨN
COLOR_CEIL, COLOR_GREEN, COLOR_REF = '#cc00ff', '#00e676', '#f5b041'
COLOR_RED, COLOR_DRED, COLOR_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU
# ==========================================
def fetch_url_with_proxies(target_url, is_json=True):
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
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=300)
def get_dynamic_top_100():
    sector_dict = get_company_sectors()
    tickers = list(sector_dict.keys())
    
    def fetch_ticker(ticker):
        try:
            df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
            if len(df) >= 2:
                close_today = df.iloc[-1]['close']
                close_yest = df.iloc[-2]['close']
                return {
                    'Mã CK': ticker, 'Nhóm Ngành': sector_dict.get(ticker, 'Khác'),
                    'Giá': close_today, '+/-': round(close_today - close_yest, 2),
                    '%': round(((close_today - close_yest) / close_yest) * 100, 2),
                    'Tổng KL': int(df.iloc[-1]['volume'])
                }
        except: return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0: results.append(res)
                
    df_market = pd.DataFrame(results)
    if not df_market.empty: return df_market.sort_values(by='Tổng KL', ascending=False).head(100)
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_realtime_index():
    return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

@st.cache_data(ttl=60)
def get_index_contrib():
    url = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['ticker', 'point']]
        df.columns, df['Điểm'] = ['Mã CK', 'Điểm'], pd.to_numeric(df['Điểm'] if not df.empty else 0)
        return df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily_ma():
    try:
        df = stock_historical_data('VNINDEX', start_hist_ma, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            return df.dropna().reset_index(drop=True)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_cafef_reports():
    url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    html = fetch_url_with_proxies(url, is_json=False)
    res = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m, s_m, d_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b), re.search(r'class="doc_source"[^>]*>(.*?)</span>', b), re.search(r'class="doc_date"[^>]*>(.*?)</span>', b)
            if t_m and l_m:
                title, link = t_m.group(1).strip(), "https://s.cafef.vn" + l_m.group(1)
                tk_match = re.search(r'\b([A-Z0-9]{3})\b', title)
                ticker = tk_match.group(1) if tk_match else ""
                
                action, t_up = "ĐÁNH GIÁ", title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): action = "MUA"
                elif any(w in t_up for w in ["BÁN", "SELL"]): action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): action = "NẮM GIỮ"
                
                res.append({"Ngày": d_m.group(1).strip() if d_m else "", "Mã CK": ticker, "Khuyến nghị": action, "CTCK": s_m.group(1).strip() if s_m else "", "Nội dung": title, "Link Tải": link})
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN 5 TABS HỢP NHẤT
# ==========================================
with st.spinner("Đang tổng hợp toàn bộ dữ liệu thị trường..."):
    df_top100 = get_dynamic_top_100()
    df_index = get_realtime_index()
    df_c = get_index_contrib()
    df_ma = get_vnindex_daily_ma()
    df_reports = get_cafef_reports()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ dòng tiền", 
    "📊 Top 100 Active", 
    "📝 Cập nhật Khuyến nghị", 
    "🤖 AI Nhận định"
])

# Hàm màu sắc dùng chung
def get_text_color(val):
    if pd.isna(val): return ''
    if val >= 6.8: return f'color: {COLOR_CEIL}; font-weight: bold;'
    elif val <= -6.8: return f'color: {COLOR_FLOOR}; font-weight: bold;'
    elif val > 0: return f'color: {COLOR_GREEN}; font-weight: bold;'
    elif val == 0: return f'color: {COLOR_REF}; font-weight: bold;'
    elif val > -3.0: return f'color: {COLOR_RED}; font-weight: bold;'
    else: return f'color: {COLOR_DRED}; font-weight: bold;'

# TAB 1: VN-INDEX
with tab1:
    if not df_index.empty:
        df_index['date'] = pd.to_datetime(df_index['time']).dt.date
        unique_dates = df_index['date'].unique()
        if len(unique_dates) >= 2:
            today_date, yest_date = unique_dates[-1], unique_dates[-2]
            df_today, df_yest = df_index[df_index['date'] == today_date].copy(), df_index[df_index['date'] == yest_date].copy()
            current_score, latest_time, ref_price = df_today.iloc[-1]['close'], df_today.iloc[-1]['time'], df_yest.iloc[-1]['close']
            
            st.metric(label=f"VN-INDEX (Lúc: {latest_time})", value=f"{current_score:,.2f}", delta=f"{current_score - ref_price:+,.2f} điểm ({(current_score - ref_price) / ref_price * 100:+,.2f}%)")
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🌊 Biểu đồ Thanh khoản")
                df_today['time_str'], df_yest['time_str'] = pd.to_datetime(df_today['time']).dt.strftime('%H:%M'), pd.to_datetime(df_yest['time']).dt.strftime('%H:%M')
                df_today['cum_vol'], df_yest['cum_vol'] = df_today['volume'].cumsum(), df_yest['volume'].cumsum()
                
                fig_liq = go.Figure()
                fig_liq.add_trace(go.Scatter(x=df_yest['time_str'], y=df_yest['cum_vol'], fill='tozeroy', mode='lines', name='Hôm qua', line=dict(color='rgba(65, 105, 225, 0.6)')))
                fig_liq.add_trace(go.Scatter(x=df_today['time_str'], y=df_today['cum_vol'], fill='tozeroy', mode='lines', name='Hôm nay', line=dict(color='rgba(154, 205, 50, 0.9)')))
                fig_liq.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350, legend=dict(orientation="h", y=1.02, x=1))
                st.plotly_chart(fig_liq, use_container_width=True)

            with col2:
                st.markdown("#### 🎯 Tác động điểm số")
                if not df_c.empty:
                    df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                    fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=[COLOR_GREEN if v > 0 else COLOR_RED for v in df_res['Điểm']], text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                    fig_b.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350)
                    st.plotly_chart(fig_b, use_container_width=True)

# TAB 2: HEATMAP
with tab2:
    if not df_top100.empty:
        custom_color_scale = [[0.0, COLOR_FLOOR], [0.014, COLOR_FLOOR], [0.014, COLOR_DRED], [0.285, COLOR_DRED], [0.285, COLOR_RED], [0.499, COLOR_RED], [0.499, COLOR_REF], [0.501, COLOR_REF], [0.501, COLOR_GREEN], [0.985, COLOR_GREEN], [0.985, COLOR_CEIL], [1.0, COLOR_CEIL]]
        fig = px.treemap(df_top100, path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=custom_color_scale, range_color=[-7, 7], custom_data=['%', 'Tổng KL'])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%<br>KL: %{customdata[1]:,.0f}", textposition="middle center", textfont=dict(color="white", size=13))
        st.plotly_chart(fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=600), use_container_width=True)

# TAB 3: BẢNG GIÁ
with tab3:
    if not df_top100.empty:
        st.markdown("### 📊 Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất")
        try: styled_df = df_top100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(get_text_color, subset=['+/-', '%'])
        except: styled_df = df_top100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).applymap(get_text_color, subset=['+/-', '%'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

# TAB 4: KHUYẾN NGHỊ CAFEF
with tab4:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị Phân Tích (CafeF)")
        st.dataframe(df_reports.style.map(lambda v: f'color: {COLOR_GREEN if "MUA" in str(v) else COLOR_RED if "BÁN" in str(v) else COLOR_REF}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link Tải": st.column_config.LinkColumn("Bấm để xem")}, hide_index=True, use_container_width=True, height=600)

# TAB 5: AI NHẬN ĐỊNH
with tab5:
    if not df_ma.empty and not df_top100.empty and not df_index.empty:
        c, ma, v, v_ma = df_index.iloc[-1]['close'], df_ma.iloc[-1]['MA20'], df_index[df_index['date'] == df_index['date'].unique()[-1]]['volume'].sum(), df_ma.iloc[-1]['V_MA20']
        adv, dec = len(df_top100[df_top100['%'] > 0]), len(df_top100[df_top100['%'] < 0])
        ai_score, vol_ratio = 0, (v / v_ma) * 100 if v_ma > 0 else 0
        
        if vol_ratio >= 120: kl_st, kl_col = f"BÙNG NỔ ({vol_ratio:.1f}% MA20)", COLOR_CEIL; ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80: kl_st, kl_col = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20)", COLOR_GREEN; ai_score += 1
        else: kl_st, kl_col = f"SUY YẾU ({vol_ratio:.1f}% MA20)", COLOR_RED
            
        if adv > dec * 1.5: rong_st, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm)", COLOR_GREEN; ai_score += 1
        elif dec > adv * 1.5: rong_st, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm)", COLOR_RED; ai_score -= 1
        else: rong_st, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm)", COLOR_REF
        
        gia_st, gia_col = ("NẰM TRÊN", COLOR_GREEN) if c > ma else ("RƠI XUỐNG DƯỚI", COLOR_RED)
        
        st.markdown(f"<div class='card'><h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ (REAL-TIME)</h2><ul style='font-size: 17px; line-height: 1.8;'><li><b>Động lượng Khối lượng:</b> {v/1000000:,.1f} Tr CP. Đánh giá: <b style='color:{kl_col}'>{kl_st}</b></li><li><b>Độ rộng thị trường (Rổ 100 mã):</b> Đánh giá: <b style='color:{rong_col}'>{rong_st}</b></li><li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f}).</li></ul></div><br>", unsafe_allow_html=True)
        
        if ai_score >= 1: sc_color, sc_title, sc_desc = COLOR_GREEN, "🟢 Kịch Bản Tích Cực", "Gia tăng tỷ trọng cổ phiếu."
        elif ai_score == 0: sc_color, sc_title, sc_desc = COLOR_REF, "🟡 Kịch Bản Đi Ngang", "Hạn chế MUA MỚI, giữ tỷ trọng cân bằng."
        else: sc_color, sc_title, sc_desc = COLOR_RED, "🔴 Kịch Bản Điều Chỉnh", "Quản trị rủi ro tuyệt đối, hạ tỷ trọng Margin."

        st.markdown(f"<div style='background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; border-left: 5px solid {sc_color};'><h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3><p style='font-size:16px;'>{sc_desc}</p></div>", unsafe_allow_html=True)

if is_trading_hours:
    time.sleep(60)
    st.rerun()
