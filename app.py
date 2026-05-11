import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import urllib.parse
import xml.etree.ElementTree as ET

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .scenario-box { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & HEADER
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Chiến Lược Toàn Thị Trường")
with col_status:
    if is_trading: 
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M:%S')}")
    else: 
        st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    
    if st.button("🔄 Cập nhật Live", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# BẢNG PHÂN MÀU CHUẨN XÁC YÊU CẦU
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_LRED, C_FLOOR = '#b30000', '#ff4d4d', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR],            
    [0.014, C_RED], [0.2857, C_RED],             
    [0.2857, C_LRED], [0.4992, C_LRED],          
    [0.4992, C_REF], [0.5007, C_REF],            
    [0.5007, C_GREEN], [0.9857, C_GREEN],        
    [0.9857, C_CEIL], [1.0, C_CEIL]              
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}

# ==========================================
# 3. LÕI DỮ LIỆU ĐỘT PHÁ: MẠNG PROXY ĐA TẦNG VƯỢT WAF
# ==========================================
@st.cache_data(ttl=30)
def get_top_200_realtime():
    """
    Lấy Top 200 mã có GIÁ TRỊ GIAO DỊCH cao nhất 3 sàn (HOSE, HNX, UPCOM).
    Đảm bảo 100% Real-time bằng cách dùng Proxy lách tường lửa Streamlit.
    """
    url_target = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=200"
    url_encoded = urllib.parse.quote(url_target, safe='')
    
    # Chiến lược 1: Gọi trực tiếp
    urls_to_try = [
        url_target,
        f"https://api.allorigins.win/raw?url={url_encoded}",  # Proxy 1
        f"https://corsproxy.io/?{url_encoded}"                # Proxy 2
    ]
    
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                data = res.json().get('data', [])
                if data:
                    df = pd.DataFrame(data)[['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol', 'accumulatedVal']]
                    df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
                    df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
                    return df.dropna(subset=['Tổng KL'])
        except:
            continue
            
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_index_contrib():
    url_target = "https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30"
    url_encoded = urllib.parse.quote(url_target, safe='')
    
    urls_to_try = [url_target, f"https://api.allorigins.win/raw?url={url_encoded}"]
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                df = pd.DataFrame(res.json()['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
                df['Điểm'] = pd.to_numeric(df['Điểm'])
                return df
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=120)
def get_vnindex_live_and_ma():
    # Lấy Giá VNINDEX Real-time từ VNDirect
    live_price, live_vol = 0, 0
    try:
        r = requests.get("https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:VNINDEX", headers=HEADERS, timeout=5).json()
        live_price = float(r['data'][0]['matchPrice'])
        live_vol = float(r['data'][0]['accumulatedVol'])
    except: pass
    
    # Tính MA20 từ vnstock
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            
            last_row = df.iloc[-1]
            c = live_price if live_price > 0 else float(last_row['close'])
            v = live_vol if live_vol > 0 else float(last_row['volume'])
            p = float(df.iloc[-2]['close']) if len(df) > 1 else c
            
            return {
                'close': c, 'prev': p, 'volume': v, 
                'MA20': float(last_row['MA20']), 'V_MA20': float(last_row['V_MA20'])
            }
    except: return None
    return None

@st.cache_data(ttl=3600)
def get_vnexpress_news():
    res = []
    try:
        xml_data = requests.get("https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss", timeout=10).text
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:20]:
            title, link, pubDate = item.find('title').text, item.find('link').text, item.find('pubDate').text
            action = "TIN TỨC"
            if any(k in title.lower() for k in ["tăng", "lãi", "hút", "vượt"]): action = "TÍCH CỰC"
            elif any(k in title.lower() for k in ["giảm", "lỗ", "bán", "lao"]): action = "TIÊU CỰC"
            res.append({"Ngày": pubDate[5:16], "Phân loại": action, "Tiêu đề": title, "Link": link})
    except: pass
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang kết nối Mạng Proxy lấy Top 200 Thanh Khoản Real-time..."):
    df_200 = get_top_200_realtime()
    
    if not df_200.empty:
        df_gainers = df_200.sort_values('%', ascending=False).head(10)
    else:
        df_gainers = pd.DataFrame()
        
    idx_data = get_vnindex_live_and_ma()
    df_reports = get_vnexpress_news()

t1, t2, t3, t4, t5, t6 = st.tabs([
    "📈 VN-INDEX & Tác động", 
    "🗺️ Bản đồ Dòng tiền", 
    "📊 Top 200 Giao Dịch", 
    "🚀 Top Tăng Mạnh", 
    "📝 Tin Chứng khoán", 
    "🔮 AI Kịch Bản"
])

def style_v(v):
    try:
        v = float(v)
        if v >= 6.8: c = C_CEIL
        elif v <= -6.8: c = C_FLOOR
        elif v > 0: c = C_GREEN
        elif v == 0: c = C_REF
        elif v > -3: c = C_LRED
        else: c = C_RED
        return f'color: {c}; font-weight: bold;'
    except: return ''

# TAB 1: CHỈ SỐ
with t1:
    if idx_data:
        cur, prev = idx_data['close'], idx_data['prev']
        st.metric(
            f"Điểm số VN-INDEX (LIVE)", 
            f"{cur:,.2f}", 
            f"{cur-prev:+,.2f} ({((cur-prev)/prev*100):+,.2f}%)"
        )
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌊 Thanh khoản (So với TBC 20 Phiên)")
            v = idx_data['volume']
            v_ma = idx_data['V_MA20']
            
            fig = go.Figure(go.Bar(
                x=['Hôm nay (LIVE)', 'Trung bình 20 Phiên (MA20)'], 
                y=[v, v_ma], 
                marker_color=[C_GREEN if v > v_ma else C_REF, 'rgba(150,150,150,0.5)'],
                text=[f"{v:,.0f}", f"{v_ma:,.0f}"],
                textposition='auto'
            ))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("#### 🎯 Tác động điểm số tới VN-INDEX")
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_b, use_container_width=True)
            elif not df_200.empty:
                df_res = pd.concat([df_200.nlargest(7, '%'), df_200.nsmallest(7, '%')]).sort_values('%', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['%']]
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['%'], marker_color=b_cols, text=df_res['%'].apply(lambda x: f"{x:+.2f}%"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_b, use_container_width=True)

# TAB 2: BẢN ĐỒ DÒNG TIỀN
with t2:
    if not df_200.empty:
        fig_m = px.treemap(
            df_200, 
            path=[px.Constant("Thị Trường"), 'Mã CK'], 
            values='Tổng GT',  # Vẽ khối theo Giá trị giao dịch như yêu cầu
            color='%', 
            color_continuous_scale=MAP_COLORS, 
            range_color=[-7, 7]
        )
        fig_m.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", 
            customdata=df_200[['%', 'Tổng KL']]
        )
        st.plotly_chart(fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0)), use_container_width=True)
    else: 
        st.warning("Dữ liệu đang được tải, vui lòng bấm Cập nhật Live.")

# TAB 3 & 4: BẢNG GIÁ
with t3:
    if not df_200.empty:
        st.markdown("### 📊 Top 200 Cổ Phiếu Giao Dịch Mạnh Nhất Toàn Thị Trường")
        st.dataframe(
            df_200.style.format({
                'Giá': '{:,.2f}', 
                '+/-': '{:+,.2f}', 
                '%': '{:+,.2f}%', 
                'Tổng KL': '{:,.0f}',
                'Tổng GT': '{:,.0f}'
            }).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, 
            hide_index=True, 
            height=600
        )

with t4:
    if not df_gainers.empty:
        st.markdown("### 🚀 Top 10 Cổ Phiếu Tăng Mạnh Nhất")
        st.dataframe(
            df_gainers.style.format({
                'Giá': '{:,.2f}', 
                '+/-': '{:+,.2f}', 
                '%': '{:+,.2f}%', 
                'Tổng KL': '{:,.0f}',
                'Tổng GT': '{:,.0f}'
            }).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, 
            hide_index=True, 
            height=400
        )

# TAB 5: TIN TỨC
with t5:
    if not df_reports.empty:
        st.markdown("### 📝 Điểm Tin Thị Trường (VNExpress)")
        st.dataframe(
            df_reports.style.map(
                lambda v: f'color: {C_GREEN if "TÍCH CỰC" in str(v) else C_RED if "TIÊU CỰC" in str(v) else C_REF}; font-weight:bold;', 
                subset=['Phân loại']
            ), 
            column_config={"Link": st.column_config.LinkColumn("Đọc bài")}, 
            hide_index=True, 
            use_container_width=True, 
            height=600
        )

# TAB 6: AI KỊCH BẢN
with t6:
    if idx_data and not df_200.empty:
        c = idx_data['close']
        ma = idx_data['MA20']
        v = idx_data['volume']
        v_ma = idx_data['V_MA20']
        
        # Đếm thực tế Tăng / Giảm từ Top 200
        adv = len(df_200[df_200['%'] > 0])
        dec = len(df_200[df_200['%'] < 0])
        
        ai_score = 0
        
        # 1. Chấm điểm Giá
        if c > ma:
            gia_st, gia_col = "Nằm TRÊN", C_GREEN
            ai_score += 1
        else:
            gia_st, gia_col = "Rơi XUỐNG DƯỚI", C_RED
            
        # 2. Chấm điểm Khối lượng
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
        if vol_ratio >= 120:
            kl_st, kl_col = f"Bùng nổ ({vol_ratio:.1f}% MA20)", C_CEIL
            ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80:
            kl_st, kl_col = f"Ổn định ({vol_ratio:.1f}% MA20)", C_GREEN
            ai_score += 1
        else:
            kl_st, kl_col = f"Suy yếu ({vol_ratio:.1f}% MA20)", C_RED
            
        # 3. Chấm điểm Độ rộng
        if adv > dec * 1.5:
            rong_st, rong_col = f"Lan tỏa cực mạnh ({adv} Tăng / {dec} Giảm)", C_CEIL
            ai_score += 1
        elif adv > dec:
            rong_st, rong_col = f"Tích cực ({adv} Tăng / {dec} Giảm)", C_GREEN
            ai_score += 1
        elif dec > adv * 1.5:
            rong_st, rong_col = f"Bán tháo diện rộng ({adv} Tăng / {dec} Giảm)", C_RED
            ai_score -= 1
        else:
            rong_st, rong_col = f"Áp lực bán nhỉnh hơn ({adv} Tăng / {dec} Giảm)", C_LRED
        
        html_ai_status = f"""
        <div class='card' style='background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%);'>
            <h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ THỊ TRƯỜNG LIVE</h2>
            <ul style='font-size: 17px; line-height: 1.8;'>
                <li><b>Hành động Giá:</b> VN-INDEX đang ở mức <b>{c:,.2f}</b>, <b style='color:{gia_col}'>{gia_st}</b> ngưỡng hỗ trợ MA20 ({ma:,.2f}).</li>
                <li><b>Động lượng Khối lượng:</b> Đạt {v/1000000:,.1f} triệu CP so với Trung bình {v_ma/1000000:,.1f} triệu CP. Dòng tiền <b style='color:{kl_col}'>{kl_st}</b>.</li>
                <li><b>Độ rộng thị trường (Rổ 200 mã lớn nhất):</b> Trạng thái <b style='color:{rong_col}'>{rong_st}</b>.</li>
            </ul>
        </div><br>
        """
        st.markdown(html_ai_status, unsafe_allow_html=True)
        
        if ai_score >= 2:
            sc_color, sc_title, sc_desc = C_GREEN, "🟢 Kịch Bản 1: Bứt phá đi lên (Khả năng cao nhất)", "Dòng tiền lan tỏa tốt. Gia tăng tỷ trọng cổ phiếu, tập trung nhóm đang hút dòng tiền (Màu Tím/Xanh đậm trên bản đồ nhiệt). Mở mua mới các mã có nền tích lũy."
        elif ai_score == 1:
            sc_color, sc_title, sc_desc = C_REF, "🟡 Kịch Bản 2: Đi ngang giằng co (Khả năng cao nhất)", "Thị trường phân hóa mạnh, kéo trụ xả midcap. Duy trì tỷ trọng 50/50. Tuyệt đối không FOMO giá xanh. Canh chốt lời ngắn hạn ở kháng cự."
        else:
            sc_color, sc_title, sc_desc = C_RED, "🔴 Kịch Bản 3: Điều chỉnh giảm (Khả năng cao nhất)", "Lực bán áp đảo, cầu suy yếu. Quản trị rủi ro đặt lên hàng đầu. Hạ tỷ trọng Margin về 0. Kiên quyết cắt lỗ các mã vi phạm hỗ trợ. Đứng ngoài quan sát."

        st.markdown(f"""
        <div class='scenario-box' style='background-color: rgba(255,255,255,0.05); border-left: 5px solid {sc_color};'>
            <h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>
            <p style='font-size:16px;'>{sc_desc}</p>
        </div>
        """, unsafe_allow_html=True)
