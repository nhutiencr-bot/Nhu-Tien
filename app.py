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

# 1. CÀI ĐẶT GIAO DIỆN
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

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist_ma = (current_time - timedelta(days=60)).strftime('%Y-%m-%d')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# CÁC HÀM TIỆN ÍCH BỔ SUNG (PROXY & DATA)
# ==========================================
def fetch_url_with_proxies(target_url, is_json=True):
    encoded = urllib.parse.quote(target_url, safe='')
    url_proxy1 = f"https://api.codetabs.com/v1/proxy?quest={encoded}"
    url_proxy2 = f"https://api.allorigins.win/raw?url={encoded}"
    
    for url in [target_url, url_proxy1, url_proxy2]:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200 and len(res.content) > 50:
                return res.json() if is_json else res.text
        except: continue
    return None

@st.cache_data(ttl=60)
def get_index_contrib():
    url = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['ticker', 'point']]
        df.columns = ['Mã CK', 'Điểm']
        df['Điểm'] = pd.to_numeric(df['Điểm'])
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
    
    p_li = r'<li.*?>(.*?)</li>'
    p_title = r'class="doc_title"[^>]*>(.*?)</a>'
    p_link = r'href="(/Report/Download\.aspx\?id=[^"]+)"'
    p_src = r'class="doc_source"[^>]*>(.*?)</span>'
    p_date = r'class="doc_date"[^>]*>(.*?)</span>'
    p_tk = r'\b([A-Z0-9]{3})\b'
    
    if html:
        for b in re.findall(p_li, html, re.DOTALL):
            t_m, l_m, s_m, d_m = re.search(p_title, b), re.search(p_link, b), re.search(p_src, b), re.search(p_date, b)
            if t_m and l_m:
                title = t_m.group(1).strip()
                link = "https://s.cafef.vn" + l_m.group(1)
                tk_match = re.search(p_tk, title)
                ticker = tk_match.group(1) if tk_match else ""
                
                action = "ĐÁNH GIÁ"
                t_up = title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): action = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): action = "NẮM GIỮ"
                
                res.append({
                    "Ngày": d_m.group(1).strip() if d_m else "", 
                    "Mã CK": ticker, 
                    "Khuyến nghị": action, 
                    "CTCK": s_m.group(1).strip() if s_m else "", 
                    "Nội dung": title, 
                    "Link Báo Cáo": link
                })
    return pd.DataFrame(res)

# 3. HÀM QUÉT TOÀN THỊ TRƯỜNG VÀ TÌM TOP 100 
@st.cache_data(ttl=86400)
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except:
        return {}

@st.cache_data(ttl=120)
def get_dynamic_top_100():
    sector_dict = get_company_sectors()
    tickers = list(sector_dict.keys())
    
    def fetch_ticker(ticker):
        try:
            df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
            if len(df) >= 2:
                close_today = df.iloc[-1]['close']
                close_yest = df.iloc[-2]['close']
                change = close_today - close_yest
                pct_change = (change / close_yest) * 100
                volume = df.iloc[-1]['volume']
                return {
                    'Mã CK': ticker,
                    'Nhóm Ngành': sector_dict.get(ticker, 'Khác'),
                    'Giá': close_today,
                    '+/-': round(change, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                }
        except:
            return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0:
                results.append(res)
                
    df_market = pd.DataFrame(results)
    if not df_market.empty:
        df_market = df_market.sort_values(by='Tổng KL', ascending=False).head(100)
    return df_market

# 4. TẠO GIAO DIỆN 5 TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ dòng tiền", 
    "📊 Top 100 Active", 
    "📝 Báo cáo CafeF", 
    "🤖 AI Nhận định"
])

# THIẾT LẬP DẢI MÀU CHUYÊN NGHIỆP
COLOR_CEIL = '#cc00ff'  
COLOR_GREEN = '#00e676' 
COLOR_REF = '#f5b041'   
COLOR_RED = '#ff4d4d'   
COLOR_DRED = '#b30000'  
COLOR_FLOOR = '#00e5ff' 

custom_color_scale = [
    [0.0, COLOR_FLOOR], [0.014, COLOR_FLOOR],    
    [0.014, COLOR_DRED], [0.285, COLOR_DRED],    
    [0.285, COLOR_RED], [0.499, COLOR_RED],      
    [0.499, COLOR_REF], [0.501, COLOR_REF],      
    [0.501, COLOR_GREEN], [0.985, COLOR_GREEN],  
    [0.985, COLOR_CEIL], [1.0, COLOR_CEIL]       
]

# TẢI DỮ LIỆU TOP 100
df_top100 = get_dynamic_top_100()

# ==========================================
# TAB 1: VN-INDEX REALTIME & ĐÓNG GÓP
# ==========================================
with tab1:
    @st.cache_data(ttl=60)
    def get_realtime_index():
        return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

    try:
        df_index = get_realtime_index()
        if not df_index.empty:
            df_index['date'] = pd.to_datetime(df_index['time']).dt.date
            unique_dates = df_index['date'].unique()
            
            if len(unique_dates) >= 2:
                today_date, yest_date = unique_dates[-1], unique_dates[-2]
                df_today = df_index[df_index['date'] == today_date].copy()
                df_yest = df_index[df_index['date'] == yest_date].copy()
                
                current_score = df_today.iloc[-1]['close']
                latest_time = df_today.iloc[-1]['time']
                ref_price = df_yest.iloc[-1]['close']
                
                point_change = current_score - ref_price
                pct_change = (point_change / ref_price) * 100
                
                st.metric(
                    label=f"VN-INDEX (Cập nhật lúc: {latest_time})", 
                    value=f"{current_score:,.2f}", 
                    delta=f"{point_change:+,.2f} điểm ({pct_change:+,.2f}%)"
                )
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 🌊 Biểu đồ Thanh khoản")
                    df_today['time_str'] = pd.to_datetime(df_today['time']).dt.strftime('%H:%M')
                    df_yest['time_str'] = pd.to_datetime(df_yest['time']).dt.strftime('%H:%M')
                    df_today['cum_vol'] = df_today['volume'].cumsum()
                    df_yest['cum_vol'] = df_yest['volume'].cumsum()
                    
                    fig_liq = go.Figure()
                    fig_liq.add_trace(go.Scatter(x=df_yest['time_str'], y=df_yest['cum_vol'], fill='tozeroy', mode='lines', name=f'Hôm qua', line=dict(color='rgba(65, 105, 225, 0.6)', width=2), fillcolor='rgba(65, 105, 225, 0.1)'))
                    fig_liq.add_trace(go.Scatter(x=df_today['time_str'], y=df_today['cum_vol'], fill='tozeroy', mode='lines', name=f'Hôm nay', line=dict(color='rgba(154, 205, 50, 0.9)', width=2), fillcolor='rgba(154, 205, 50, 0.5)'))
                    fig_liq.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_liq, use_container_width=True)
                
                with c2:
                    st.markdown("### 🎯 Tác động điểm số (Theo CP lưu hành)")
                    df_c = get_index_contrib()
                    if not df_c.empty:
                        df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                        b_cols = [COLOR_GREEN if v > 0 else COLOR_RED for v in df_res['Điểm']]
                        fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=30,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_b, use_container_width=True)
    except Exception as e:
        st.error("Đang chờ dữ liệu VN-INDEX...")

# ==========================================
# TAB 2: BẢN ĐỒ NHIỆT (HEATMAP DÒNG TIỀN)
# ==========================================
with tab2:
    if not df_top100.empty:
        fig = px.treemap(
            df_top100, 
            path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], 
            values='Tổng KL', color='%', 
            color_continuous_scale=custom_color_scale, range_color=[-7, 7],
            custom_data=['%', 'Tổng KL', 'Giá']
        )
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%<br>KL: %{customdata[1]:,.0f}", textposition="middle center", textfont=dict(color="white", size=13))
        fig.update_layout(margin=dict(t=20, l=10, r=10, b=10), height=650)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⏳ Đang tải dữ liệu Bản đồ nhiệt...")

# ==========================================
# TAB 3: BẢNG ĐIỆN TOP 100
# ==========================================
with tab3:
    if not df_top100.empty:
        st.markdown("### 📊 Biến động 100 cổ phiếu có thanh khoản lớn nhất")
        def get_text_color(val):
            if pd.isna(val): return ''
            if val >= 6.8: return f'color: {COLOR_CEIL}; font-weight: bold;'
            elif val <= -6.8: return f'color: {COLOR_FLOOR}; font-weight: bold;'
            elif val > 0: return f'color: {COLOR_GREEN}; font-weight: bold;'
            elif val == 0: return f'color: {COLOR_REF}; font-weight: bold;'
            elif val > -3.0: return f'color: {COLOR_RED}; font-weight: bold;'
            else: return f'color: {COLOR_DRED}; font-weight: bold;'
            
        format_dict = {'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}
        
        try: styled_df = df_top100.style.format(format_dict).map(get_text_color, subset=['+/-', '%'])
        except: styled_df = df_top100.style.format(format_dict).applymap(get_text_color, subset=['+/-', '%'])
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
    else:
        st.info("⏳ Đang tải dữ liệu Bảng điện...")

# ==========================================
# TAB 4: BÁO CÁO CAFEF
# ==========================================
with tab4:
    df_reports = get_cafef_reports()
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị Phân Tích (CafeF)")
        st.dataframe(
            df_reports.style.map(lambda v: f'color: {COLOR_GREEN if "MUA" in str(v) else COLOR_RED if "BÁN" in str(v) else COLOR_REF}; font-weight:bold;', subset=['Khuyến nghị']), 
            column_config={"Link Báo Cáo": st.column_config.LinkColumn("Tải xuống")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else:
        st.warning("Đang chờ dữ liệu khuyến nghị...")

# ==========================================
# TAB 5: AI NHẬN ĐỊNH THỊ TRƯỜNG
# ==========================================
with tab5:
    df_ma = get_vnindex_daily_ma()
    if not df_ma.empty and not df_top100.empty and 'df_index' in locals() and not df_index.empty:
        # Giá và Khối lượng hiện tại
        c = df_index.iloc[-1]['close']
        v = df_index[df_index['date'] == df_index['date'].unique()[-1]]['volume'].sum()
        
        # MA20
        ma = df_ma.iloc[-1]['MA20']
        v_ma = df_ma.iloc[-1]['V_MA20']
        
        # Độ rộng từ Top 100
        adv = len(df_top100[df_top100['%'] > 0])
        dec = len(df_top100[df_top100['%'] < 0])
        
        ai_score = 0
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
        
        if vol_ratio >= 120:
            kl_st, kl_col = f"BÙNG NỔ ({vol_ratio:.1f}% MA20). Dòng tiền vào mạnh mẽ.", COLOR_CEIL
            ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80:
            kl_st, kl_col = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20). Khối lượng duy trì tự nhiên.", COLOR_GREEN
            ai_score += 1
        else:
            kl_st, kl_col = f"SUY YẾU ({vol_ratio:.1f}% MA20). Lực cầu còn dè dặt.", COLOR_RED
            
        if adv > dec * 1.5:
            rong_st, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm).", COLOR_GREEN
            ai_score += 1
        elif dec > adv * 1.5:
            rong_st, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm). Dấu hiệu bán diện rộng.", COLOR_RED
            ai_score -= 1
        else:
            rong_st, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm).", COLOR_REF
        
        gia_st = "NẰM TRÊN" if c > ma else "RƠI XUỐNG DƯỚI"
        gia_col = COLOR_GREEN if c > ma else COLOR_RED
        
        html_ai_status = (
            "<div class='card'>"
            "<h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TRẠNG THÁI (REAL-TIME)</h2>"
            "<ul style='font-size: 17px; line-height: 1.8;'>"
            f"<li><b>Động lượng Khối lượng:</b> {v/1000000:,.1f} Tr CP. Đánh giá: <b style='color:{kl_col}'>{kl_st}</b></li>"
            f"<li><b>Độ rộng thị trường (Rổ 100 mã):</b> Đánh giá: <b style='color:{rong_col}'>{rong_st}</b></li>"
            f"<li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f}).</li>"
            "</ul>"
            "</div><br>"
        )
        st.markdown(html_ai_status, unsafe_allow_html=True)
        
        if ai_score >= 1: 
            sc_color, sc_title, sc_desc = COLOR_GREEN, "🟢 Kịch Bản Tích Cực", "Khối lượng gia tăng và độ rộng thị trường lan tỏa. Gia tăng tỷ trọng cổ phiếu."
        elif ai_score == 0: 
            sc_color, sc_title, sc_desc = COLOR_REF, "🟡 Kịch Bản Đi Ngang", "Khối lượng suy yếu hoặc số mã giảm đang nhỉnh hơn. Hạn chế MUA MỚI, giữ tỷ trọng cân bằng."
        else: 
            sc_color, sc_title, sc_desc = COLOR_RED, "🔴 Kịch Bản Điều Chỉnh Giảm", "Hiện tượng bán tháo rõ rệt. Quản trị rủi ro tuyệt đối, hạ tỷ trọng Margin."

        st.markdown(
            f"<div style='background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; border-left: 5px solid {sc_color};'>"
            f"<h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>"
            f"<p style='font-size:16px;'>{sc_desc}</p>"
            "</div>", unsafe_allow_html=True
        )

# Tự động làm mới trang sau 60 giây
time.sleep(60)
st.rerun()
