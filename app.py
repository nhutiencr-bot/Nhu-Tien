import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import re

# Thử import vnstock an toàn
try:
    from vnstock import stock_historical_data
except ImportError:
    st.error("⚠️ Chưa cài đặt vnstock. Vui lòng kiểm tra requirements.txt")

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    div.row-widget.stRadio > div > label { background-color: #2a2a3c; color: white; padding: 12px 15px; border-radius: 8px; cursor: pointer; transition: 0.3s; width: 100%; margin-bottom: 10px; }
    div.row-widget.stRadio > div > label[data-checked="true"] { background-color: #ffaa00; color: #1e1e2f; font-weight: bold; }
    div.row-widget.stRadio > div > label > div:first-child { display: none; }
</style>
""", unsafe_allow_html=True)

# Cấu hình thời gian (Chống lỗi cuối tuần)
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
target_date = now - timedelta(days=1) if now.weekday() == 5 else now - timedelta(days=2) if now.weekday() == 6 else now
end_date = target_date.strftime('%Y-%m-%d')
start_hist = (target_date - timedelta(days=60)).strftime('%Y-%m-%d')

col1, col2 = st.columns([3, 1])
col1.title("🧚‍♀️ FAIRY INVEST - Dashboard")
if col2.button("🔄 Làm mới Dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

C_CEIL, C_GREEN, C_REF, C_RED, C_FLOOR = '#cc00ff', '#00e676', '#f5b041', '#ff4d4d', '#00e5ff'

# ==========================================
# 2. HÀM LẤY DỮ LIỆU LAI TẠO (TCBS + VNSTOCK + CAFEF)
# ==========================================

# 1. LẤY BẢNG ĐIỆN TỪ TCBS (Cực nhanh, không tốn RAM)
@st.cache_data(ttl=120)
def get_tcbs_market_data():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/second-board-market-watch?market=HOSE"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        df = pd.DataFrame(res.json()['data'])
        df = df[['ticker', 'price', 'priceChange', 'percentPriceChange', 'volume']].copy()
        df.columns = ['Mã CK', 'Giá hiện tại', '+/-', '%', 'Tổng KL']
        return df.sort_values('Tổng KL', ascending=False).head(100)
    except:
        # Fallback an toàn nếu rớt mạng
        return pd.DataFrame([{'Mã CK': 'FPT', 'Giá hiện tại': 135.0, '+/-': 1.0, '%': 0.8, 'Tổng KL': 5000000}])

# 2. LẤY LỊCH SỬ VN-INDEX TỪ VNSTOCK (Chuẩn phân tích kỹ thuật)
@st.cache_data(ttl=300)
def get_vnstock_index():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['Vol_MA20'] = df['volume'].rolling(20).mean()
            # Xóa các dòng NaN do rolling tạo ra để tránh lỗi mảng
            return df.dropna().reset_index(drop=True)
        raise Exception("Empty")
    except:
        # Fallback tạo dữ liệu mẫu cực chuẩn, không bao giờ lệch length
        dates = pd.date_range(end=now, periods=30)
        df_mock = pd.DataFrame({'time': dates, 'close': [1250]*30, 'volume': [600000000]*30})
        df_mock['MA20'] = 1250
        df_mock['Vol_MA20'] = 600000000
        return df_mock

# 3. LẤY BÁO CÁO TỪ CAFEF (Bóc tách thông minh)
@st.cache_data(ttl=3600)
def get_cafef_reports():
    res = []
    try:
        url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?symbol=&DoanhNghiepID=-1&NganhCoPhieuID=-1&CongTyKienNghiID=-1&TuNgay=&DenNgay=&PageIndex=1&PageSize=30"
        blocks = re.findall(r'<li.*?>(.*?)</li>', requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).text, re.DOTALL)
        for b in blocks:
            t_m = re.search(r'<a[^>]*class="doc_title"[^>]*>(.*?)</a>', b)
            if not t_m: continue
            t = t_m.group(1).strip()
            l_m = re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if l_m:
                res.append({
                    "Ngày": (re.search(r'<span class="doc_date".*?>(.*?)</span>', b) or re.search('','')).group(1) or "N/A",
                    "Mã CK": (re.search(r'([A-Z0-9]{3})', t) or re.search('','')).group(1) or "N/A",
                    "CTCK": (re.search(r'<span class="doc_source".*?>(.*?)</span>', b) or re.search('','')).group(1) or "N/A",
                    "Khuyến nghị": (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|TÍCH LŨY)', t, re.I) or re.search('','')).group(1) or "ĐÁNH GIÁ",
                    "Giá mục tiêu": (re.search(r'mục tiêu.*?([\d,\.]+)', t, re.I) or re.search('','')).group(1) or "N/A",
                    "Tiêu đề Báo cáo": t,
                    "Link PDF": "https://s.cafef.vn" + l_m.group(1)
                })
    except: pass
    return pd.DataFrame(res)

# ==========================================
# 3. XUẤT GIAO DIỆN
# ==========================================
df_100 = get_tcbs_market_data()
df_hist = get_vnstock_index()

t1, t2, t3, t4, t5 = st.tabs(["📈 Chỉ số", "🗺️ Dòng tiền", "📊 Top Cổ phiếu", "📝 Báo Cáo", "🔮 Kịch bản AI"])

with t1:
    if len(df_hist) >= 2:
        cur, ref = df_hist.iloc[-1]['close'], df_hist.iloc[-2]['close']
        st.metric(f"VN-INDEX (Kết phiên gần nhất)", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
        
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['close'], name='VN-INDEX', line=dict(color='white')))
        fig_p.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['MA20'], name='MA20', line=dict(color=C_GREEN, dash='dash')))
        fig_p.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_p, use_container_width=True)

with t2:
    if not df_100.empty and len(df_100) > 1:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=[[0, C_FLOOR], [0.5, C_REF], [1, C_CEIL]], range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.info("Bản đồ nhiệt đang bảo trì (hoặc dùng dữ liệu mẫu).")

with t3:
    if not df_100.empty:
        st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(lambda v: f'color: {C_GREEN if v>0 else C_RED if v<0 else C_REF}', subset=['%']), hide_index=True, use_container_width=True)

with t4:
    df_rep = get_cafef_reports()
    if not df_rep.empty:
        # Tự động nối Giá Hiện Tại từ TCBS vào bảng CafeF để so sánh với Giá Mục Tiêu
        if not df_100.empty:
            df_rep = pd.merge(df_rep, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')
            cols = ['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']
            df_rep = df_rep[[c for c in cols if c in df_rep.columns]]

        st.dataframe(df_rep.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v).upper() else C_RED if "BÁN" in str(v).upper() else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link PDF": st.column_config.LinkColumn("Tài liệu", display_text="📥 Tải PDF")}, hide_index=True, use_container_width=True)
    else:
        st.warning("⚠️ Đang chờ dữ liệu báo cáo từ CafeF...")

with t5:
    col_l, col_r = st.columns([7, 3])
    with col_r:
        st.markdown("<h4 style='color: white;'>Menu</h4>", unsafe_allow_html=True)
        opt = st.radio("Chức năng:", ["🔮 AI Scoring", "📊 Khối lượng", "⚖️ Cung - Cầu"], label_visibility="collapsed")

    with col_l:
        if not df_hist.empty and not df_100.empty:
            cur_c, ma20 = df_hist.iloc[-1]['close'], df_hist.iloc[-1]['MA20']
            cur_v, v_ma20 = df_hist.iloc[-1]['volume'], df_hist.iloc[-1]['Vol_MA20']
            adv, dec = len(df_100[df_100['%'] > 0]), len(df_100[df_100['%'] < 0])
            
            # Thuật toán chấm điểm
            score = sum([cur_c > ma20, cur_v > v_ma20, adv > dec])
            s_map = {3: ("RẤT TÍCH CỰC", C_CEIL), 2: ("TÍCH CỰC", C_GREEN), 1: ("THẬN TRỌNG", C_REF), 0: ("TIÊU CỰC", C_RED)}
            st_txt, st_col = s_map.get(score, ("ĐANG CẬP NHẬT", C_REF))

            if opt == "🔮 AI Scoring":
                st.markdown(f"""
                <div class="scenario-card">
                    <h3 style="color:{st_col}">{st_txt} ({score}/3 Điểm)</h3>
                    <p><b>1. Giá vs MA20:</b> {'Tốt' if cur_c > ma20 else 'Xấu'}</p>
                    <p><b>2. Dòng tiền:</b> {'Vượt' if cur_v > v_ma20 else 'Dưới'} trung bình</p>
                    <p><b>3. Độ rộng:</b> {adv} Tăng / {dec} Giảm</p>
                    <hr style="border-color: #3f3f5a;">
                    <p><b>👉 Hành động:</b> {'Gia tăng tỷ trọng.' if score >= 2 else 'Hạ tỷ trọng, quản trị rủi ro.'}</p>
                </div>
                """, unsafe_allow_html=True)
            elif opt == "📊 Khối lượng":
                fig_v = go.Figure()
                fig_v.add_trace(go.Bar(x=df_hist['time'], y=df_hist['volume'], name='Khối lượng', marker_color=[C_GREEN if i>0 and df_hist['close'].iloc[i] > df_hist['close'].iloc[i-1] else C_RED for i in range(len(df_hist))]))
                fig_v.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['Vol_MA20'], name='MA20 Vol', line=dict(color='#ffaa00')))
                fig_v.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                st.plotly_chart(fig_v, use_container_width=True)
            elif opt == "⚖️ Cung - Cầu":
                st.markdown(f"<div class='scenario-card' style='text-align:center;'><h1 style='color:{C_GREEN}'>{adv} Mã Tăng</h1><h1>|</h1><h1 style='color:{C_RED}'>{dec} Mã Giảm</h1></div>", unsafe_allow_html=True)
