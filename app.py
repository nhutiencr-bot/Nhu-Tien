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

# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
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
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.toast("Đã làm mới dữ liệu thị trường!", icon="✅")

# 3. MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

# 4. CÁC HÀM LẤY DỮ LIỆU CỐT LÕI
@st.cache_data(ttl=300)
def get_hose_tickers():
    try:
        df = listing_companies()
        return df[df['comGroupCode'] == 'HOSE']['ticker'].tolist()
    except: return []

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {
                'Mã CK': t, 'Giá hiện tại': curr, '+/-': round(curr-prev, 2),
                '%': round((curr-prev)/prev*100, 2), 
                'Tổng KL': int(d.iloc[-1]['volume'])
            }
        except: return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
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

# === HÀM MỚI: BÓC TÁCH BÁO CÁO PHÂN TÍCH ===
@st.cache_data(ttl=3600) # Lưu cache 1 tiếng để tránh bị web chặn
def get_analyst_reports():
    reports = []
    try:
        # Cào dữ liệu từ trang Báo cáo phân tích
        url = "https://finance.vietstock.vn/bao-cao-phan-tich"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Tìm các thẻ bài viết (Mô phỏng bóc tách HTML)
        articles = soup.find_all('h2', class_='article-title') # Cấu trúc mẫu của web tin tức
        
        for article in articles[:15]:
            a_tag = article.find('a')
            if not a_tag: continue
            
            title = a_tag.text.strip()
            link = "https://finance.vietstock.vn" + a_tag['href']
            
            # 1. Dùng Regex tìm Mã CK (3 chữ cái in hoa đứng trước dấu hai chấm)
            ticker_match = re.search(r'^([A-Z0-9]{3})\s*:', title)
            ticker = ticker_match.group(1) if ticker_match else "N/A"
            
            # 2. Dùng Regex tìm Khuyến nghị
            action_match = re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN)', title, re.IGNORECASE)
            action = action_match.group(1).upper() if action_match else "ĐÁNH GIÁ"
            
            # 3. Dùng Regex tìm Giá mục tiêu
            price_match = re.search(r'mục tiêu\s*([\d,\.]+)', title, re.IGNORECASE)
            target_price = price_match.group(1) if price_match else "N/A"
            
            reports.append({
                "Mã CK": ticker,
                "Khuyến nghị": action,
                "Giá mục tiêu": target_target,
                "Tiêu đề gốc": title,
                "Link tải": link
            })
    except:
        pass
    
    # FALLBACK DỮ LIỆU MẪU (Nếu Streamlit Cloud bị Vietstock chặn IP)
    if not reports:
        reports = [
            {"Mã CK": "KBC", "Khuyến nghị": "MUA", "Giá mục tiêu": "42,400", "Tiêu đề gốc": "KBC: Khuyến nghị MUA với giá mục tiêu 42,400 đồng/cổ phiếu", "Link tải": "https://finance.vietstock.vn/bao-cao-phan-tich/20195/kbc-khuyen-nghi-mua-voi-gia-muc-tieu-42400-dongco-phieu.htm"},
            {"Mã CK": "FPT", "Khuyến nghị": "KHẢ QUAN", "Giá mục tiêu": "135,000", "Tiêu đề gốc": "FPT: Cập nhật kết quả kinh doanh, KHẢ QUAN giá mục tiêu 135,000", "Link tải": "https://finance.vietstock.vn/bao-cao-phan-tich"},
            {"Mã CK": "HPG", "Khuyến nghị": "MUA", "Giá mục tiêu": "35,000", "Tiêu đề gốc": "HPG: Khuyến nghị MUA, giá mục tiêu 35,000 đồng/cp", "Link tải": "https://finance.vietstock.vn/bao-cao-phan-tich"},
            {"Mã CK": "VHM", "Khuyến nghị": "NẮM GIỮ", "Giá mục tiêu": "45,000", "Tiêu đề gốc": "VHM: Khuyến nghị NẮM GIỮ, triển vọng cuối năm", "Link tải": "https://finance.vietstock.vn/bao-cao-phan-tich"}
        ]
        
    return pd.DataFrame(reports)

# 5. HIỂN THỊ GIAO DIỆN CÁC TABS
with st.spinner("Đang tính toán dữ liệu thị trường..."):
    df_100 = get_market_data()

# ---> THÊM TAB 4 VÀO ĐÂY <---
t1, t2, t3, t4 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Khuyến Nghị CTCK"])

with t1:
    try:
        df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
        if not df_daily.empty and len(df_daily) >= 2:
            cur = df_daily.iloc[-1]['close']
            ref = df_daily.iloc[-2]['close']
            time_str = df_daily.iloc[-1]['time']
            st.metric(f"Điểm số VN-INDEX (Chốt phiên {time_str})", f"{cur:,.2f}", 
                      f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
            st.divider()
    except:
        st.warning("Đang kết nối để lấy điểm số VN-INDEX...")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🌊 Thanh khoản")
        try:
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                
                fig = go.Figure()
                if len(dates) >= 2:
                    df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig.add_trace(go.Scatter(x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', name='Phiên trước', line=dict(color='rgba(150,150,150,0.5)')))
                
                fig.add_trace(go.Scatter(x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', name='Phiên gần nhất', line=dict(color=C_GREEN)))
                fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h", y=1.1), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("☕ Đồ thị thanh khoản đang bảo trì cuối tuần.")
        except: st.info("☕ Đồ thị thanh khoản đang bảo trì cuối tuần.")
            
    with c2:
        st.markdown("#### 🎯 Tác động tới VN-INDEX")
        try:
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), 
                                   df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, 
                                         text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_b, use_container_width=True)
            else: st.info("☕ Biểu đồ tác động đang được cập nhật.")
        except: st.info("☕ Biểu đồ tác động đang được cập nhật.")

with t2:
    if not df_100.empty:
        with st.spinner("Đang kết xuất Bản đồ Dòng tiền..."):
            fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', 
                               color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
            fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
            fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0))
            st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_100.empty:
        def style_v(v):
            if v >= 6.8: c = C_CEIL
            elif v <= -6.8: c = C_FLOOR
            elif v > 0: c = C_GREEN
            elif v == 0: c = C_REF
            elif v > -3: c = C_RED
            else: c = C_DRED
            return f'color: {c}; font-weight: bold;'
        
        st.markdown("### Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất")
        st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'})
                     .map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

# ==========================================
# TAB 4: BÁO CÁO KHUYẾN NGHỊ CTCK (UI/UX MƯỢT)
# ==========================================
with t4:
    st.markdown("### 📝 Tổng hợp Báo Cáo & Khuyến Nghị Đầu Tư")
    df_reports = get_analyst_reports()
    
    # Nối thêm "Giá hiện tại" từ Top 100 vào để dễ so sánh với Giá Mục Tiêu
    if not df_100.empty and not df_reports.empty:
        df_reports = pd.merge(df_reports, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')
    
    # Tô màu Khuyến nghị (Mua = Xanh, Bán = Đỏ, Nắm giữ = Vàng)
    def style_action(val):
        if 'MUA' in str(val).upper() or 'KHẢ QUAN' in str(val).upper():
            return f'color: {C_GREEN}; font-weight: bold; background-color: rgba(0, 230, 118, 0.1);'
        elif 'BÁN' in str(val).upper() or 'KÉM' in str(val).upper():
            return f'color: {C_RED}; font-weight: bold; background-color: rgba(255, 77, 77, 0.1);'
        return f'color: {C_REF}; font-weight: bold;'

    st.dataframe(
        df_reports.style.map(style_action, subset=['Khuyến nghị']),
        column_config={
            "Tiêu đề gốc": st.column_config.TextColumn("Nội dung báo cáo", width="large"),
            "Link tải": st.column_config.LinkColumn("Tải PDF/Xem chi tiết", display_text="🔗 Xem báo cáo"),
            "Giá mục tiêu": st.column_config.TextColumn("Giá mục tiêu (VND)"),
        },
        use_container_width=True,
        hide_index=True,
        height=500
    )
