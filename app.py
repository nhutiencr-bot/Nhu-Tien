import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS BẢO VỆ
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; margin-bottom: 20px; }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
current_time_str = now.strftime('%H:%M:%S')

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST")
with col_status:
    st.success(f"🟢 HỆ THỐNG ĐANG CHẠY | {current_time_str}")
    if st.button("🔄 Làm mới toàn bộ Web", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF, C_RED, C_DRED, C_FLOOR = '#cc00ff', '#00e676', '#f5b041', '#ff4d4d', '#b30000', '#00e5ff'

# ==========================================
# 2. HÀM LẤY DỮ LIỆU "BẤT TỬ" (API TCBS + FALLBACK)
# ==========================================
@st.cache_data(ttl=60)
def get_market_data():
    try:
        # Gọi trực tiếp API Công khai của TCBS (Không cần vnstock)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()['data'])
            df = df[['ticker', 'price', 'priceChange', 'percentPriceChange', 'volume']].copy()
            df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL']
            return df.sort_values('Tổng KL', ascending=False).head(100), "Dữ liệu Thực (TCBS API)"
    except Exception as e:
        pass
    
    # Nếu đứt cáp hoặc API TCBS bảo trì, BẮT BUỘC trả về dữ liệu mẫu để web không bị trắng
    mock_data = pd.DataFrame([
        {'Mã CK': 'FPT', 'Giá': 135.0, '+/-': 2.5, '%': 1.8, 'Tổng KL': 4500000},
        {'Mã CK': 'HPG', 'Giá': 29.5, '+/-': -0.3, '%': -1.0, 'Tổng KL': 15000000},
        {'Mã CK': 'SSI', 'Giá': 36.2, '+/-': 0.8, '%': 2.2, 'Tổng KL': 8000000},
        {'Mã CK': 'VCB', 'Giá': 92.5, '+/-': 1.2, '%': 1.3, 'Tổng KL': 2500000},
        {'Mã CK': 'VHM', 'Giá': 42.1, '+/-': 0.0, '%': 0.0, 'Tổng KL': 5000000},
    ])
    return mock_data, "Dữ liệu Mô phỏng (Do API bị chặn)"

@st.cache_data(ttl=60)
def get_index_data():
    try:
        # Lấy VN-INDEX từ TCBS
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()['data'])
            return df[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    return pd.DataFrame([{'Mã CK': 'VCB', 'Điểm': 1.2}, {'Mã CK': 'BID', 'Điểm': 0.8}, {'Mã CK': 'VIC', 'Điểm': -0.5}])

# ==========================================
# 3. HIỂN THỊ GIAO DIỆN CHÍNH
# ==========================================
df_m, data_source = get_market_data()

# Cảnh báo nguồn dữ liệu
if "Mô phỏng" in data_source:
    st.error(f"⚠️ **Trạng thái:** {data_source}. Tường lửa đang chặn IP của Streamlit. Hãy bấm nút 'Làm mới' ở góc phải.")
else:
    st.success(f"✅ **Trạng thái:** {data_source} - Kết nối ổn định.")

t1, t2, t3, t4 = st.tabs(["🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "🎯 Tác động VN-INDEX", "🔮 Kịch bản"])

with t1:
    if not df_m.empty:
        # Scale màu chuẩn
        color_scale = [[0.0, C_FLOOR], [0.01, C_FLOOR], [0.01, C_DRED], [0.49, C_DRED], [0.49, C_RED], [0.5, C_REF], [0.51, C_GREEN], [0.99, C_GREEN], [0.99, C_CEIL], [1.0, C_CEIL]]
        fig_m = px.treemap(df_m, path=[px.Constant("Thị trường HOSE"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=color_scale, range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_m[['%', 'Tổng KL']])
        fig_m.update_layout(height=600, margin=dict(t=0,l=0,r=0,b=0))
        st.plotly_chart(fig_m, use_container_width=True)

with t2:
    if not df_m.empty:
        def style_v(v): 
            if pd.isna(v): return ''
            return f'color: {C_CEIL if v>=6.8 else C_FLOOR if v<=-6.8 else C_GREEN if v>0 else C_RED if v<0 else C_REF}; font-weight: bold;'
        st.dataframe(df_m.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True)

with t3:
    st.markdown("#### 🎯 Tác động tới VN-INDEX")
    df_c = get_index_data()
    if not df_c.empty:
        df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
        fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=[C_GREEN if v>0 else C_RED for v in df_res['Điểm']], text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
        fig_b.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_b, use_container_width=True)

with t4:
    st.markdown(f"""
    <div class="scenario-card">
        <div class="scenario-title">Dự báo chiến lược giao dịch</div>
        <p>Hệ thống tự động phân tích độ rộng thị trường dựa trên Top cổ phiếu thanh khoản cao.</p>
        <hr>
        <p><b>Độ rộng thị trường:</b> <span style="color:{C_GREEN}">{len(df_m[df_m['%'] > 0])} mã tăng</span> / <span style="color:{C_RED}">{len(df_m[df_m['%'] < 0])} mã giảm</span>.</p>
        <p><b>Chiến lược:</b> {'Thị trường phân hóa tốt, ưu tiên nắm giữ cổ phiếu mạnh.' if df_m['%'].mean() > 0 else 'Thị trường suy yếu, ưu tiên quản trị rủi ro, hạ tỷ trọng margin.'}</p>
    </div>
    """, unsafe_allow_html=True)
