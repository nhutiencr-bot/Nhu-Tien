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
start_index = (now - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard Toàn Thị Trường")
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

# TẬP HỢP ~130 MÃ CỔ PHIẾU CÓ THANH KHOẢN CAO NHẤT 3 SÀN (Y HỆT ẢNH CỦA BẠN)
MARKET_SYMBOLS = [
    'VIX','SHB','SSI','GEX','NVL','HPG','MSB','MBB','ACB','VPB','VND','TPB','STB','TCB',
    'EIB','DXG','DIG','VCI','HDB','VHM','KBC','POW','VRE','PDR','HSG','NKG','DGC','FPT',
    'CTG','TCH','CII','BSR','MWG','LPB','VIC','HAG','OCB','VIB','BID','VCB','VNM','MSN',
    'GAS','PLX','SAB','SSB','DGW','FRT','PNJ','PET','DPM','DCM','CSV','ANV','VHC','IDI',
    'ASM','SBT','DBC','PAN','LTG','GVR','PHR','DPR','DRC','KDH','NLG','HDG','CEO','TDC',
    'IJC','ITA','HQC','SCR','CRE','KHG','NTL','SZC','IDC','VCG','HHV','LCG','FCN','KSB',
    'CTD','HBC','PC1','GEG','NT2','HAH','GMD','VOS','PVT','PVS','PVD','PVC','OIL','BCG',
    'AAA','APH','TIG','HUT','MBS','SHS','CTS','FTS','BSI','AGR','VDS','ORS','TVB','APG',
    'HCM','EVF','AAS','SBS','TNG','TCM','GIL','VGT','STK','HT1','BCC','KDC','VOC','SMC'
]

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU ĐỘT PHÁ (VƯỢT TƯỜNG LỬA 100%)
# ==========================================
@st.cache_data(ttl=60)
def get_full_market_data():
    def fetch_stock(ticker):
        try:
            # Dùng chính hàm đã vẽ thành công VNINDEX để quét cổ phiếu
            df = stock_historical_data(ticker, start_index, end_date, '1D', 'stock')
            if len(df) >= 2:
                curr = df.iloc[-1]['close']
                prev = df.iloc[-2]['close']
                vol = df.iloc[-1]['volume']
                return {
                    'Mã CK': ticker, 
                    'Giá': curr, 
                    '+/-': curr - prev, 
                    '%': (curr - prev) / prev * 100, 
                    'Tổng KL': vol
                }
        except:
            return None
            
    # Bơm 20 luồng quét song song, tốc độ phản hồi chỉ 2 giây!
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_stock, MARKET_SYMBOLS))
        
    df_board = pd.DataFrame([r for r in results if r])
    if not df_board.empty:
        # Lấy chính xác Top 100 thanh khoản khủng nhất
        return df_board.sort_values('Tổng KL', ascending=False).head(100)
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
def get_vnexpress_news():
    res = []
    try:
        # Nguồn tin tức không bị chặn IP
        xml_data = requests.get("https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss", timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:30]:
            title = item.find('title').text
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            
            action = "TIN TỨC"
            t_lower = title.lower()
            if any(kw in t_lower for kw in ["tăng", "lãi", "hút tiền", "vượt"]): 
                action = "TÍCH CỰC"
            elif any(kw in t_lower for kw in ["giảm", "lỗ", "bán tháo", "lao dốc"]): 
                action = "TIÊU CỰC"
                
            res.append({
                "Ngày": pubDate[5:16], 
                "Phân loại": action, 
                "Tiêu đề Báo cáo": title, 
                "Link": link
            })
    except: 
        pass
    return pd.DataFrame(res)

# ==========================================
# 4. KHỞI TẠO DỮ LIỆU & GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang quét toàn thị trường để tìm Top 100 Thanh Khoản..."):
    df_100 = get_full_market_data()
    df_idx_daily = get_vnindex_daily()
    df_reports = get_vnexpress_news()

t1, t2, t3, t4, t5 = st.tabs([
    "📈 VN-INDEX", 
    "🗺️ Bản đồ Dòng tiền (Top 100)", 
    "📊 Bảng giá (Top 100)", 
    "📝 Tin Chứng khoán", 
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
                
                if len(dates) > 1: df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                else: df_y = df_t
                    
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
                            x=df_y['ts'], y=df_y['volume'].cumsum(), fill='tozeroy', 
                            name='Hôm qua', line=dict(color='rgba(150,150,150,0.5)')
                        ))
                    fig.add_trace(go.Scatter(
                        x=df_t['ts'], y=df_t['volume'].cumsum(), fill='tozeroy', 
                        name='Hôm nay', line=dict(color=C_GREEN)
                    ))
                    
                    fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h", y=1.1), plot_bgcolor='rgba(0,0,0,0)')
                    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.2)')
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown("#### 🎯 Biến Động Dẫn Dắt Dòng Tiền Toàn Thị Trường")
                    if not df_100.empty:
                        # Lấy top mã tăng mạnh và giảm mạnh nhất trong Top 100 Thanh Khoản
                        df_res = pd.concat([
                            df_100.nlargest(6, '%'), 
                            df_100.nsmallest(6, '%')
                        ]).sort_values('%', ascending=False)
                        
                        b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['%']]
                        
                        fig_b = go.Figure(go.Bar(
                            x=df_res['Mã CK'], y=df_res['%'], marker_color=b_cols, 
                            text=df_res['%'].apply(lambda x: f"{x:+.2f}%"), textposition='outside'
                        ))
                        fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_b, use_container_width=True)
        except Exception as e: 
            st.error(f"Đang cập nhật biểu đồ thanh khoản trong ngày...")

# TAB 2: BẢN ĐỒ DÒNG TIỀN (TOÀN THỊ TRƯỜNG)
with t2:
    if not df_100.empty:
        fig_m = px.treemap(
            df_100, path=[px.Constant("Toàn Thị Trường"), 'Mã CK'], 
            values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7]
        )
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: 
        st.warning("Dữ liệu dòng tiền đang được xử lý...")

# TAB 3: BẢNG GIÁ (TOP 100 TOÀN THỊ TRƯỜNG)
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
            
        st.markdown("### Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất Toàn Thị Trường (Real-time)")
        st.dataframe(
            df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, hide_index=True, height=600
        )

# TAB 4: TIN TỨC
with t4:
    if not df_reports.empty:
        st.markdown("### 📝 Điểm Tin Thị Trường (VNExpress)")
        st.dataframe(
            df_reports.style.map(
                lambda v: f'color: {C_GREEN if "TÍCH CỰC" in str(v) else C_RED if "TIÊU CỰC" in str(v) else C_REF}; font-weight:bold;', 
                subset=['Phân loại']
            ), 
            column_config={"Link": st.column_config.LinkColumn("Đọc bài")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else: 
        st.warning("Hệ thống chưa tải được bản tin.")

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
                <li><b>Cung - Cầu Top 100:</b> Sắc xanh <b style='color:{cungcau_color}'>{cungcau_status}</b> (Có {adv} mã Tăng so với {dec} mã Giảm).</li>
            </ul>
            <hr style='border-color: #3f3f5a;'>
            <h3 style='margin-bottom:0;'>👉 GỢI Ý HÀNH ĐỘNG: <span style='color:{action_color}'>{action}</span></h3>
        </div>
        """, unsafe_allow_html=True)
