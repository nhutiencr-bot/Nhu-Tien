import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import xml.etree.ElementTree as ET

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
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
    .card { 
        background-color: #1e1e2f; 
        padding: 25px; 
        border-radius: 10px; 
        border-left: 5px solid #ffaa00; 
        color: white; 
        margin-top: 10px; 
    }
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
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading: 
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else: 
        st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU
# ==========================================
@st.cache_data(ttl=60)
def get_market_data():
    try:
        url = (
            "https://finfo-api.vndirect.com.vn/v4/stock_prices"
            "?sort=accumulatedVol~DESC&q=floor:HOSE&size=100"
        )
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        df = pd.DataFrame(res['data'])[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol']]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
        df[['Giá', '+/-', '%', 'Tổng KL']] = df[['Giá', '+/-', '%', 'Tổng KL']].apply(pd.to_numeric)
        return df
    except: 
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = (
            "https://finfo-api.vndirect.com.vn/v4/index_events"
            "?q=code:VNINDEX&sort=point~DESC&size=50"
        )
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        df = pd.DataFrame(res['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    except: 
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'] = df['close'].rolling(20).mean()
        df['V_MA20'] = df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: 
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef_rss():
    res = []
    try:
        url = "https://cafef.vn/rss/chung-khoan.rss"
        xml_data = requests.get(url, headers=HEADERS, timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:30]:
            title = item.find('title').text
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            
            match = re.search(r'\b([A-Z]{3})\b', title)
            ticker = match.group(1) if match else "Thị trường"
            
            action = "TIN TỨC"
            if "mua" in title.lower() or "tăng" in title.lower():
                action = "CHÚ Ý"
            elif "bán" in title.lower() or "giảm" in title.lower():
                action = "CẢNH BÁO"
                
            res.append({
                "Ngày": pubDate[5:16], 
                "Mã CK": ticker, 
                "Đánh giá": action, 
                "Tiêu đề Báo cáo": title, 
                "Link": link
            })
    except: 
        pass
    return pd.DataFrame(res)

# ==========================================
# 4. KHỞI TẠO DỮ LIỆU & GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang kết nối siêu tốc lấy Dữ liệu VNDirect..."):
    df_100 = get_market_data()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_cafef_rss()

t1, t2, t3, t4, t5 = st.tabs([
    "📈 VN-INDEX & Đóng góp", 
    "🗺️ Bản đồ Dòng tiền", 
    "📊 Top 100 Cổ phiếu", 
    "📝 Báo cáo CafeF", 
    "🔮 AI Kịch Bản"
])

# TAB 1: CHỈ SỐ
with t1:
    with st.spinner("Đang vẽ biểu đồ VN-INDEX..."):
        try:
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if not df_idx.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                
                if len(dates) > 1:
                    df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                else:
                    df_y = df_t
                    
                cur = df_t.iloc[-1]['close']
                ref = df_y.iloc[-1]['close']
                
                st.metric(
                    f"Điểm số VN-INDEX (Lúc {df_t.iloc[-1]['time']})", 
                    f"{cur:,.2f}", 
                    f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)"
                )
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🌊 Thanh khoản (Hôm nay vs Hôm qua)")
                    df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    
                    fig = go.Figure()
                    if len(dates) > 1: 
                        fig.add_trace(go.Scatter(
                            x=df_y['ts'], y=df_y['volume'].cumsum(), 
                            fill='tozeroy', name='Hôm qua', 
                            line=dict(color='rgba(150,150,150,0.5)')
                        ))
                    fig.add_trace(go.Scatter(
                        x=df_t['ts'], y=df_t['volume'].cumsum(), 
                        fill='tozeroy', name='Hôm nay', 
                        line=dict(color=C_GREEN)
                    ))
                    
                    fig.update_layout(
                        height=380, margin=dict(l=10,r=10,t=10,b=10), 
                        legend=dict(orientation="h", y=1.1), 
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown("#### 🎯 Tác động tới VN-INDEX (Free-float)")
                    df_c = get_index_contrib()
                    if not df_c.empty:
                        df_res = pd.concat([
                            df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), 
                            df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')
                        ]).sort_values('Điểm', ascending=False)
                        
                        b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                        
                        fig_b = go.Figure(go.Bar(
                            x=df_res['Mã CK'], 
                            y=df_res['Điểm'], 
                            marker_color=b_cols, 
                            text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), 
                            textposition='outside'
                        ))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_b, use_container_width=True)
        except Exception as e: 
            st.error(f"Đang cập nhật biểu đồ thanh khoản trong ngày...")

# TAB 2: BẢN ĐỒ DÒNG TIỀN
with t2:
    if not df_100.empty:
        fig_m = px.treemap(
            df_100, 
            path=[px.Constant("Thị trường"), 'Mã CK'], 
            values='Tổng KL', 
            color='%', 
            color_continuous_scale=MAP_COLORS, 
            range_color=[-7, 7]
        )
        fig_m.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", 
            customdata=df_100[['%', 'Tổng KL']]
        )
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: 
        st.warning("Dữ liệu dòng tiền đang được xử lý...")

# TAB 3: TOP 100
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
        st.dataframe(
            df_100.style.format({
                'Giá': '{:,.2f}', 
                '+/-': '{:+,.2f}', 
                '%': '{:+,.2f}%', 
                'Tổng KL': '{:,.0f}'
            }).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, 
            hide_index=True, 
            height=600
        )

# TAB 4: CAFEF
with t4:
    if not df_reports.empty:
        st.markdown("### 📝 Tổng hợp Phân Tích & Tin tức (Nguồn: CafeF)")
        st.dataframe(
            df_reports.style.map(
                lambda v: f'color: {C_GREEN if "CHÚ Ý" in str(v) else C_RED if "CẢNH BÁO" in str(v) else C_REF}; font-weight:bold;', 
                subset=['Đánh giá']
            ), 
            column_config={"Link": st.column_config.LinkColumn("Đọc ngay")}, 
            hide_index=True, 
            use_container_width=True, 
            height=600
        )
    else: 
        st.warning("Hệ thống chưa tải được bản tin từ CafeF.")

# TAB 5: AI SCORING
with t5:
    if not df_idx_daily.empty and not df_100.empty:
        c = df_idx_daily.iloc[-1]['close']
        ma = df_idx_daily.iloc[-1]['MA20']
        v = df_idx_daily.iloc[-1]['volume']
        v_ma = df_idx_daily.iloc[-1]['V_MA20']
        
        adv = len(df_100[df_100['%'] > 0])
        dec = len(df_100[df_100['%'] < 0])
        
        score = sum([c > ma, v > v_ma, adv > dec])
        
        cols = [C_RED, C_REF, C_GREEN, C_CEIL]
        txts = ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"]
        
        gia_status = 'nằm trên' if c > ma else 'rơi xuống dưới'
        gia_color = '#00e676' if c > ma else '#ff4d4d'
        
        kl_status = 'bùng nổ vượt' if v > v_ma else 'chưa vượt qua'
        kl_color = '#00e676' if v > v_ma else '#f5b041'
        
        cungcau_status = 'áp đảo' if adv > dec else 'yếu thế'
        cungcau_color = '#00e676' if adv > dec else '#ff4d4d'
        
        action = 'Ưu tiên giải ngân, gia tăng tỷ trọng.' if score >= 2 else 'Phòng thủ, hạ tỷ trọng Margin, quan sát.'
        action_color = C_GREEN if score >= 2 else C_RED
        
        st.markdown(f"""
        <div class='card'>
            <h2 style='color:{cols[score]}; margin-top:0;'>🤖 DỰ BÁO XU HƯỚNG: {txts[score]} ({score}/3 ĐIỂM)</h2>
            <ul style='font-size: 18px; line-height: 1.8;'>
                <li><b>Kỹ thuật:</b> Giá VN-INDEX ({c:,.2f}) đang <b style='color:{gia_color}'>{gia_status}</b> đường trung bình MA20 ({ma:,.2f}).</li>
                <li><b>Dòng tiền:</b> Khối lượng giao dịch <b style='color:{kl_color}'>{kl_status}</b> mức trung bình 20 phiên.</li>
                <li><b>Cung - Cầu:</b> Sắc xanh <b style='color:{cungcau_color}'>{cungcau_status}</b> (Có {adv} mã Tăng so với {dec} mã Giảm).</li>
            </ul>
            <hr style='border-color: #3f3f5a;'>
            <h3 style='margin-bottom:0;'>👉 GỢI Ý HÀNH ĐỘNG: <span style='color:{action_color}'>{action}</span></h3>
        </div>
        """, unsafe_allow_html=True)
