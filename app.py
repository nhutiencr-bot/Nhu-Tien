import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
import concurrent.futures

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & HEADER
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_index = (now - timedelta(days=7)).strftime('%Y-%m-%d')
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

# Danh sách rổ VN30
VN30 = ['ACB','BCM','BID','BVH','CTG','FPT','GAS','GVR','HDB','HPG',
        'MBB','MSN','MWG','PLX','POW','SAB','SHB','SSB','SSI','STB',
        'TCB','TPB','VCB','VHM','VIB','VIC','VJC','VNM','VPB','VRE']

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU (DÙNG VNSTOCK & VNEXPRESS ĐỂ KHÔNG BỊ CHẶN)
# ==========================================
@st.cache_data(ttl=120)
def get_vn30_data():
    # Sử dụng hàm vnstock đã được chứng minh là không bị chặn để lấy VN30
    def fetch_ticker(t):
        try:
            df = stock_historical_data(t, start_index, end_date, '1D', 'stock')
            if len(df) >= 2:
                curr, prev = df.iloc[-1]['close'], df.iloc[-2]['close']
                vol = df.iloc[-1]['volume']
                return {'Mã CK': t, 'Giá': curr, '+/-': curr - prev, '%': (curr - prev) / prev * 100, 'Tổng KL': vol}
        except: return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(fetch_ticker, VN30))
        
    valid_results = [r for r in results if r]
    if valid_results:
        return pd.DataFrame(valid_results).sort_values('Tổng KL', ascending=False)
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_daily():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        df['MA20'], df['V_MA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
        return df.dropna().reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_vnexpress_news():
    res = []
    try:
        # Nguồn VNExpress không bao giờ chặn Streamlit
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
    return pd.DataFrame(res)

# ==========================================
# 4. KHỞI TẠO DỮ LIỆU & GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang tải dữ liệu từ VNSTOCK & VNExpress..."):
    df_board = get_vn30_data()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_vnexpress_news()

t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX", "🗺️ Dòng tiền VN30", "📊 Bảng giá VN30", "📝 Tin Chứng khoán", "🔮 AI Kịch Bản"])

# TAB 1: CHỈ SỐ
with t1:
    if not df_idx_daily.empty:
        df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
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
            st.markdown("#### 🎯 Biến động nhóm VN30 (%)")
            if not df_board.empty:
                df_res = pd.concat([df_board.nlargest(7, '%'), df_board.nsmallest(7, '%')]).sort_values('%', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['%']]
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['%'], marker_color=b_cols, text=df_res['%'].apply(lambda x: f"{x:+.1f}%"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_b, use_container_width=True)
    else: st.warning("Đang tải dữ liệu chỉ số...")

# TAB 2: BẢN ĐỒ DÒNG TIỀN VN30
with t2:
    if not df_board.empty:
        fig_m = px.treemap(df_board, path=[px.Constant("VN30"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_board[['%', 'Tổng KL']])
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: st.warning("Dữ liệu dòng tiền đang được xử lý...")

# TAB 3: BẢNG GIÁ VN30
with t3:
    if not df_board.empty:
        def style_v(v):
            if v >= 6.8: c = C_CEIL
            elif v <= -6.8: c = C_FLOOR
            elif v > 0: c = C_GREEN
            elif v == 0: c = C_REF
            elif v > -3: c = C_RED
            else: c = C_DRED
            return f'color: {c}; font-weight: bold;'
        st.markdown("### Top 30 Cổ Phiếu Dẫn Dắt Thị Trường (VN30)")
        st.dataframe(df_board.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

# TAB 4: TIN TỨC VNEXPRESS
with t4:
    if not df_reports.empty:
        st.markdown("### 📝 Tin Tức Thị Trường (Nguồn: VNExpress)")
        st.dataframe(df_reports.style.map(lambda v: f'color: {C_GREEN if "TÍCH CỰC" in str(v) else C_RED if "TIÊU CỰC" in str(v) else C_REF}; font-weight:bold;', subset=['Phân loại']), column_config={"Link": st.column_config.LinkColumn("Đọc bài")}, hide_index=True, use_container_width=True, height=600)
    else: st.warning("Hệ thống chưa tải được bản tin từ VNExpress.")

# TAB 5: AI SCORING
with t5:
    if not df_idx_daily.empty and not df_board.empty:
        c, ma, v, v_ma = df_idx_daily.iloc[-1]['close'], df_idx_daily.iloc[-1]['MA20'], df_idx_daily.iloc[-1]['volume'], df_idx_daily.iloc[-1]['V_MA20']
        adv, dec = len(df_board[df_board['%'] > 0]), len(df_board[df_board['%'] < 0])
        score = sum([c > ma, v > v_ma, adv > dec])
        
        cols, txts = [C_RED, C_REF, C_GREEN, C_CEIL], ["TIÊU CỰC", "THẬN TRỌNG", "TÍCH CỰC", "RẤT TÍCH CỰC"]
        gia_st, gia_co = ('nằm trên', '#00e676') if c > ma else ('rơi xuống dưới', '#ff4d4d')
        kl_st, kl_co = ('bùng nổ vượt', '#00e676') if v > v_ma else ('chưa vượt qua', '#f5b041')
        cc_st, cc_co = ('áp đảo', '#00e676') if adv > dec else ('yếu thế', '#ff4d4d')
        act, act_co = ('Ưu tiên giải ngân, gia tăng tỷ trọng.', C_GREEN) if score >= 2 else ('Phòng thủ, hạ tỷ trọng Margin, quan sát.', C_RED)
        
        st.markdown(f"""
        <div class='card'>
            <h2 style='color:{cols[score]}; margin-top:0;'>🤖 DỰ BÁO XU HƯỚNG: {txts[score]} ({score}/3 ĐIỂM)</h2>
            <ul style='font-size: 18px; line-height: 1.8;'>
                <li><b>Kỹ thuật:</b> Giá VN-INDEX ({c:,.2f}) đang <b style='color:{gia_co}'>{gia_st}</b> đường MA20 ({ma:,.2f}).</li>
                <li><b>Dòng tiền:</b> Khối lượng giao dịch <b style='color:{kl_co}'>{kl_st}</b> mức trung bình 20 phiên.</li>
                <li><b>Cung - Cầu VN30:</b> Sắc xanh <b style='color:{cc_co}'>{cc_st}</b> (Có {adv} mã Tăng so với {dec} mã Giảm).</li>
            </ul>
            <hr style='border-color: #3f3f5a;'>
            <h3 style='margin-bottom:0;'>👉 GỢI Ý HÀNH ĐỘNG: <span style='color:{act_co}'>{act}</span></h3>
        </div>
        """, unsafe_allow_html=True)
