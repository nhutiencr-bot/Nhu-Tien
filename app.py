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
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #00e5ff; color: white; margin-top: 10px; }
    .scenario-box { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist_ma = (current_time - timedelta(days=60)).strftime('%Y-%m-%d')

is_weekday = current_time.weekday() < 5
current_hour = current_time.hour
current_minute = current_time.minute
is_trading_hours = is_weekday and ((9 <= current_hour <= 14) or (current_hour == 15 and current_minute <= 30) or (current_hour == 8 and current_minute >= 50))

if is_trading_hours:
    st.sidebar.success(f"🟢 Thị trường đang MỞ CỬA\n\nCập nhật lúc: {current_time.strftime('%H:%M:%S')}")
else:
    st.sidebar.warning(f"🔴 Thị trường ĐÃ ĐÓNG CỬA\n\nDữ liệu chốt phiên ngày {end_date}")

# MÀU SẮC CHUẨN
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

# 3. LÕI DỮ LIỆU CŨ CỦA BẠN (CỰC KỲ ỔN ĐỊNH VÀ REAL-TIME TỐT)
@st.cache_data(ttl=86400)
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except:
        return {}

@st.cache_data(ttl=120) # Cập nhật nhanh hơn
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
        except: return None

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

@st.cache_data(ttl=60)
def get_realtime_index():
    return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

# BỔ SUNG: DỮ LIỆU ĐỂ NUÔI TAB 4 VÀ 5
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
    encoded = urllib.parse.quote(url, safe='')
    urls = [url, f"https://api.codetabs.com/v1/proxy?quest={encoded}"]
    html = ""
    for u in urls:
        try:
            res = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if res.status_code == 200 and "<li" in res.text:
                html = res.text
                break
        except: continue
        
    res_list = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            s_m, d_m = re.search(r'class="doc_source"[^>]*>(.*?)</span>', b), re.search(r'class="doc_date"[^>]*>(.*?)</span>', b)
            
            if t_m and l_m:
                title = t_m.group(1).strip()
                link = "https://s.cafef.vn" + l_m.group(1)
                tk_match = re.search(r'\b([A-Z0-9]{3})\b', title)
                ticker = tk_match.group(1) if tk_match else ""
                
                action, t_up = "ĐÁNH GIÁ", title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): action = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): action = "NẮM GIỮ"
                
                res_list.append({
                    "Ngày": d_m.group(1).strip() if d_m else "", 
                    "Mã CK": ticker, 
                    "Khuyến nghị": action, 
                    "CTCK": s_m.group(1).strip() if s_m else "", 
                    "Nội dung": title, 
                    "Link Tải PDF": link
                })
    return pd.DataFrame(res_list)

# 4. GIAO DIỆN 5 TABS HỢP NHẤT
with st.spinner("Đang tổng hợp dữ liệu toàn thị trường..."):
    df_top100 = get_dynamic_top_100()
    df_index = get_realtime_index()
    df_ma = get_vnindex_daily_ma()
    df_reports = get_cafef_reports()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ dòng tiền", 
    "📊 Top 100 Active", 
    "📝 Cập nhật Khuyến nghị", 
    "🤖 AI Nhận định"
])

def get_text_color(val):
    if pd.isna(val): return ''
    if val >= 6.8: return f'color: {COLOR_CEIL}; font-weight: bold;'
    elif val <= -6.8: return f'color: {COLOR_FLOOR}; font-weight: bold;'
    elif val > 0: return f'color: {COLOR_GREEN}; font-weight: bold;'
    elif val == 0: return f'color: {COLOR_REF}; font-weight: bold;'
    elif val > -3.0: return f'color: {COLOR_RED}; font-weight: bold;'
    else: return f'color: {COLOR_DRED}; font-weight: bold;'

# TAB 1: VN-INDEX (VỚI CÔNG THỨC IMPACT CŨ CỦA BẠN - KHÔNG BAO GIỜ LỖI)
with tab1:
    if not df_index.empty:
        df_index['date'] = pd.to_datetime(df_index['time']).dt.date
        unique_dates = df_index['date'].unique()
        
        if len(unique_dates) >= 2:
            today_date = unique_dates[-1]
            yest_date = unique_dates[-2]
            
            df_today = df_index[df_index['date'] == today_date].copy()
            df_yest = df_index[df_index['date'] == yest_date].copy()
            
            current_score = df_today.iloc[-1]['close']
            latest_time = df_today.iloc[-1]['time']
            ref_price = df_yest.iloc[-1]['close']
            
            point_change = current_score - ref_price
            pct_change = (point_change / ref_price) * 100
            
            st.metric(label=f"VN-INDEX (Cập nhật lúc: {latest_time})", value=f"{current_score:,.2f}", delta=f"{point_change:+,.2f} điểm ({pct_change:+,.2f}%)")
            st.divider()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🌊 Biểu đồ Thanh khoản (Hôm nay vs Hôm qua)")
                df_today['time_str'] = pd.to_datetime(df_today['time']).dt.strftime('%H:%M')
                df_yest['time_str'] = pd.to_datetime(df_yest['time']).dt.strftime('%H:%M')
                df_today['cum_vol'] = df_today['volume'].cumsum()
                df_yest['cum_vol'] = df_yest['volume'].cumsum()
                
                fig_liq = go.Figure()
                fig_liq.add_trace(go.Scatter(x=df_yest['time_str'], y=df_yest['cum_vol'], fill='tozeroy', mode='lines', name=f'Hôm qua', line=dict(color='rgba(65, 105, 225, 0.6)', width=2), fillcolor='rgba(65, 105, 225, 0.1)'))
                fig_liq.add_trace(go.Scatter(x=df_today['time_str'], y=df_today['cum_vol'], fill='tozeroy', mode='lines', name=f'Hôm nay', line=dict(color='rgba(154, 205, 50, 0.9)', width=2), fillcolor='rgba(154, 205, 50, 0.5)'))
                fig_liq.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_liq, use_container_width=True)

            with col2:
                st.markdown("#### 🚀 Cổ phiếu biến động mạnh (Nhóm Top 100)")
                if not df_top100.empty:
                    df_top100['Impact'] = df_top100['%'] * df_top100['Tổng KL']
                    top_pos = df_top100[df_top100['%'] > 0].sort_values('Impact', ascending=False).head(10)
                    top_neg = df_top100[df_top100['%'] < 0].sort_values('Impact', ascending=True).head(10)
                    df_impact = pd.concat([top_neg, top_pos]).sort_values('%', ascending=True)
                    
                    bar_colors = [COLOR_RED if val < 0 else COLOR_GREEN for val in df_impact['%']]
                    
                    fig_bar = go.Figure(go.Bar(
                        x=df_impact['%'], y=df_impact['Mã CK'], orientation='h',
                        marker_color=bar_colors,
                        text=df_impact['%'].apply(lambda x: f"{x:+.2f}%"),
                        textposition='outside'
                    ))
                    fig_bar.update_layout(margin=dict(l=10, r=30, t=10, b=10), height=380, xaxis_title="% Thay đổi")
                    st.plotly_chart(fig_bar, use_container_width=True)

# TAB 2: BẢN ĐỒ DÒNG TIỀN
with tab2:
    if not df_top100.empty:
        fig = px.treemap(df_top100, path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=custom_color_scale, range_color=[-7, 7], custom_data=['%', 'Tổng KL'])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%<br>KL: %{customdata[1]:,.0f}", textposition="middle center", textfont=dict(color="white", size=13))
        fig.update_layout(margin=dict(t=20, l=10, r=10, b=10), height=650)
        st.plotly_chart(fig, use_container_width=True)

# TAB 3: TOP 100 ACTIVE
with tab3:
    if not df_top100.empty:
        st.markdown("### 📊 Biến động 100 cổ phiếu có thanh khoản lớn nhất hôm nay")
        format_dict = {'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}
        try: styled_df = df_top100.style.format(format_dict).map(get_text_color, subset=['+/-', '%'])
        except: styled_df = df_top100.style.format(format_dict).applymap(get_text_color, subset=['+/-', '%'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

# TAB 4: BÁO CÁO CAFEF
with tab4:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị Phân Tích (CafeF)")
        st.dataframe(
            df_reports.style.map(lambda v: f'color: {COLOR_GREEN if "MUA" in str(v) else COLOR_RED if "BÁN" in str(v) else COLOR_REF}; font-weight:bold;', subset=['Khuyến nghị']), 
            column_config={"Link Tải PDF": st.column_config.LinkColumn("Bấm để xem")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else: st.warning("Đang chờ dữ liệu khuyến nghị...")

# TAB 5: AI NHẬN ĐỊNH VSA (VỚI TÍNH TOÁN TRIỆU CỔ PHIẾU CHUẨN)
with tab5:
    if not df_ma.empty and not df_top100.empty and not df_index.empty:
        c = df_index.iloc[-1]['close']
        ma = df_ma.iloc[-1]['MA20']
        
        # Lấy khối lượng hôm nay từ biểu đồ Real-time (1 phút)
        df_index['date'] = pd.to_datetime(df_index['time']).dt.date
        today_date = df_index['date'].unique()[-1]
        v = df_index[df_index['date'] == today_date]['volume'].sum()
        v_ma = df_ma.iloc[-1]['V_MA20']
        
        adv = len(df_top100[df_top100['%'] > 0])
        dec = len(df_top100[df_top100['%'] < 0])
        
        v_mil = v / 1000000
        vma_mil = v_ma / 1000000
        
        if v > v_ma:
            if c > ma: vol_msg, kl_col = f"Dòng tiền <b style='color:#00e676;'>MUA CHỦ ĐỘNG</b> mạnh (Đạt {v_mil:,.1f} Tr CP, vượt mức TB {vma_mil:,.1f} Tr CP).", COLOR_GREEN
            else: vol_msg, kl_col = f"Áp lực <b style='color:#ff4d4d;'>BÁN THÁO</b> lớn (Đạt {v_mil:,.1f} Tr CP, vượt mức TB {vma_mil:,.1f} Tr CP).", COLOR_RED
        else:
            if c > ma: vol_msg, kl_col = f"Thanh khoản <b style='color:#f5b041;'>THẤP</b> (Chỉ đạt {v_mil:,.1f} Tr CP, dưới mức TB {vma_mil:,.1f} Tr CP). Cầu dè dặt.", COLOR_REF
            else: vol_msg, kl_col = f"Thanh khoản <b style='color:#ff4d4d;'>SUY YẾU</b> (Đạt {v_mil:,.1f} Tr CP, dưới mức TB {vma_mil:,.1f} Tr CP). Dòng tiền vắng bóng.", COLOR_RED

        if adv > dec * 1.5: rong_msg, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm). Sắc xanh áp đảo.", COLOR_GREEN
        elif dec > adv * 1.5: rong_msg, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm). Dấu hiệu 'Xanh vỏ đỏ lòng'.", COLOR_RED
        else: rong_msg, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Luân chuyển dòng tiền.", COLOR_REF

        st.markdown(f"""
        <div class='card'>
            <h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TRẠNG THÁI (REAL-TIME)</h2>
            <ul style='font-size: 17px; line-height: 1.8;'>
                <li><b>Động lượng Khối lượng:</b> {vol_msg}</li>
                <li><b>Độ rộng thị trường (Rổ 100 mã):</b> <b style='color:{rong_col}'>{rong_msg}</b></li>
                <li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{"#00e676" if c > ma else "#ff4d4d"}'>{'NẰM TRÊN' if c > ma else 'RƠI XUỐNG DƯỚI'}</b> MA20 ({ma:,.2f}).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        score = sum([c > ma, v > v_ma, adv > dec])
        if score >= 2: sc_col, sc_ti, sc_de = COLOR_GREEN, "🟢 Kịch Bản Tích Cực", f"Sự lan tỏa diễn ra tốt.\n\n<b>Hành động:</b> Ưu tiên nắm giữ, gia tăng tỷ trọng và mở mua mới ở các mã có nền giá tích lũy chặt chẽ."
        elif score == 1: sc_col, sc_ti, sc_de = COLOR_REF, "🟡 Kịch Bản Đi Ngang", f"Trạng thái phân hóa mạnh, có hiện tượng kéo trụ.\n\n<b>Hành động:</b> Duy trì tỷ trọng cân bằng 50/50, mua bán chọn lọc, tuyệt đối không FOMO giá xanh."
        else: sc_col, sc_ti, sc_de = COLOR_RED, "🔴 Kịch Bản Rủi Ro", f"Áp lực bán lớn, thị trường mất vùng hỗ trợ.\n\n<b>Hành động:</b> Quản trị rủi ro tuyệt đối, kiên quyết hạ Margin và đứng ngoài quan sát."

        st.markdown(f"<div class='scenario-box' style='border-left: 5px solid {sc_col};'><h3 style='color:{sc_col}; margin-top:0;'>{sc_ti}</h3><p style='font-size:16px;'>{sc_de}</p></div>", unsafe_allow_html=True)

if is_trading_hours:
    time.sleep(60)
    st.rerun()
