import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import requests
import urllib.parse
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

css_code = (
    "<style>"
    "div[data-testid='stMetric'] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }"
    ".stTabs [data-baseweb='tab-list'] button [data-testid='stMarkdownContainer'] p { font-size: 17px; font-weight: 600; }"
    "div[data-testid='stDataFrame'] { border-radius: 10px; overflow: hidden; }"
    ".card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; }"
    ".scenario-box { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); }"
    "</style>"
)
st.markdown(css_code, unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_hist = (now - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Phân Tích Chuyên Sâu")
with col_status:
    if is_trading: 
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M:%S')}")
    else: 
        st.warning("🔴 ĐÃ ĐÓNG CỬA | Phiên gần nhất")
    if st.button("🔄 Cập nhật Live", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

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

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. MẠNG PROXY XUYÊN TƯỜNG LỬA CHỐNG TRẮNG TRANG
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

@st.cache_data(ttl=30)
def get_top_200_realtime():
    base_url = "https://finfo-api.vndirect.com.vn/v4/stock_prices"
    query = "?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=200"
    data = fetch_url_with_proxies(base_url + query, is_json=True)
    
    if data and 'data' in data:
        cols = ['code', 'matchPrice', 'priceChange', 'changePc', 'accumulatedVol', 'accumulatedVal']
        df = pd.DataFrame(data['data'])[cols]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
        df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
        return df.dropna(subset=['Tổng KL'])
    return pd.DataFrame()

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

@st.cache_data(ttl=120)
def get_vnindex_live_and_ma():
    live_c, live_v = 0, 0
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:VNINDEX"
    data = fetch_url_with_proxies(url, is_json=True)
    if data and 'data' in data and len(data['data']) > 0:
        live_c = float(data['data'][0].get('matchPrice', 0))
        live_v = float(data['data'][0].get('accumulatedVol', 0))
        
    try: 
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['V_MA20'] = df['volume'].rolling(20).mean()
            last = df.iloc[-1]
            c = live_c if live_c > 0 else float(last['close'])
            v = live_v if live_v > 0 else float(last['volume'])
            p = float(df.iloc[-2]['close']) if len(df) > 1 else c
            return {'close': c, 'prev': p, 'volume': v, 'MA20': float(last['MA20']), 'V_MA20': float(last['V_MA20'])}
    except: pass
    return None

@st.cache_data(ttl=1800)
def get_cafef_reports():
    url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    html = fetch_url_with_proxies(url, is_json=False)
    res = []
    
    # Biến Regex được viết ngắn gọn để không bị gãy dòng
    p_li = r'<li.*?>(.*?)</li>'
    p_title = r'class="doc_title"[^>]*>(.*?)</a>'
    p_link = r'href="(/Report/Download\.aspx\?id=[^"]+)"'
    p_src = r'class="doc_source"[^>]*>(.*?)</span>'
    p_date = r'class="doc_date"[^>]*>(.*?)</span>'
    p_tk = r'\b([A-Z0-9]{3})\b'
    
    if html:
        for b in re.findall(p_li, html, re.DOTALL):
            t_m = re.search(p_title, b)
            l_m = re.search(p_link, b)
            s_m = re.search(p_src, b)
            d_m = re.search(p_date, b)
            
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
                
                date_val = d_m.group(1).strip() if d_m else ""
                src_val = s_m.group(1).strip() if s_m else ""
                
                res.append({
                    "Ngày": date_val, 
                    "Mã CK": ticker, 
                    "Khuyến nghị": action, 
                    "CTCK": src_val, 
                    "Nội dung": title, 
                    "Link Tải PDF": link
                })
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang sử dụng Proxy Xuyên Tường Lửa (Chờ 2-3s)..."):
    df_200 = get_top_200_realtime()
    
    if not df_200.empty:
        df_gainers = df_200.sort_values('%', ascending=False).head(10)
    else:
        df_gainers = pd.DataFrame()
        
    idx_data = get_vnindex_live_and_ma()
    df_reports = get_cafef_reports()

t1, t2, t3, t4, t5, t6 = st.tabs([
    "📈 Chỉ số & Tác động", 
    "🗺️ Dòng tiền (200 Mã)", 
    "📊 Bảng giá (200 Mã)", 
    "🚀 Top 10 Tăng Mạnh", 
    "📝 Cập nhật Khuyến nghị", 
    "🔮 Phân Tích AI (VSA)"
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
        st.metric(f"Điểm số VN-INDEX (LIVE)", f"{cur:,.2f}", f"{cur-prev:+,.2f} ({((cur-prev)/prev*100):+,.2f}%)")
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌊 Thanh khoản (So với TBC 20 Phiên)")
            v, v_ma = idx_data['volume'], idx_data['V_MA20']
            
            x_data = ['Khối lượng LIVE', 'Trung bình MA20']
            y_data = [v, v_ma]
            c_data = [C_GREEN if v > v_ma else C_REF, 'rgba(150,150,150,0.5)']
            t_data = [f"{v/1000000:,.1f} Tr CP", f"{v_ma/1000000:,.1f} Tr CP"]
            
            fig = go.Figure(go.Bar(x=x_data, y=y_data, marker_color=c_data, text=t_data, textposition='auto'))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("#### 🎯 Tác động điểm số VN-INDEX")
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_b, use_container_width=True)

# TAB 2: BẢN ĐỒ DÒNG TIỀN
with t2:
    if not df_200.empty:
        fig_m = px.treemap(
            df_200, 
            path=[px.Constant("Toàn Thị Trường"), 'Mã CK'], 
            values='Tổng GT', 
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
        st.error("Tường lửa chặn gắt gao. Hãy ấn [🔄 Cập nhật Live] để hệ thống đổi IP Proxy mới.")

# TAB 3 & 4: BẢNG GIÁ
with t3:
    if not df_200.empty:
        st.markdown("### 📊 Top 200 Cổ Phiếu Dẫn Dắt Dòng Tiền Toàn Thị Trường")
        st.dataframe(
            df_200.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}', 'Tổng GT': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, hide_index=True, height=600
        )

with t4:
    if not df_gainers.empty:
        st.markdown("### 🚀 Top 10 Cổ Phiếu Tăng Mạnh Nhất")
        st.dataframe(
            df_gainers.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}', 'Tổng GT': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), 
            use_container_width=True, hide_index=True, height=400
        )

# TAB 5: KHUYẾN NGHỊ
with t5:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị (Nguồn: CafeF)")
        st.dataframe(
            df_reports.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), 
            column_config={"Link Tải PDF": st.column_config.LinkColumn("Bấm để xem")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else: 
        st.warning("Đang quét báo cáo Khuyến nghị...")

# TAB 6: AI VSA CHUYÊN SÂU
with t6:
    if idx_data and not df_200.empty:
        c, ma, v, v_ma = idx_data['close'], idx_data['MA20'], idx_data['volume'], idx_data['V_MA20']
        adv, dec = len(df_200[df_200['%'] > 0]), len(df_200[df_200['%'] < 0])
        
        ai_score = 0
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
        
        if vol_ratio >= 120:
            kl_st = f"BÙNG NỔ ({vol_ratio:.1f}% MA20). Khối lượng vượt xa mức trung bình 20 phiên ({v_ma/1000000:,.1f} Tr CP)."
            kl_col = C_CEIL
            ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80:
            kl_st = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20). Khối lượng duy trì quanh mức trung bình tự nhiên."
            kl_col = C_GREEN
            ai_score += 1
        else:
            kl_st = f"SUY YẾU ({vol_ratio:.1f}% MA20). Dòng tiền lớn đang đứng ngoài, lực cầu cạn kiệt."
            kl_col = C_RED
            
        if adv > dec * 1.5:
            rong_st = f"LAN TỎA TÍCH CỰC (Có {adv} mã Tăng áp đảo {dec} mã Giảm). Dòng tiền mua lan rộng toàn thị trường."
            rong_col = C_GREEN
            ai_score += 1
        elif dec > adv * 1.5:
            rong_st = f"CẢNH BÁO RỦI RO (Chỉ có {adv} mã Tăng nhưng tới {dec} mã Giảm). Đây là hiện tượng 'Xanh vỏ, đỏ lòng' hoặc xả hàng."
            rong_col = C_RED
            ai_score -= 1
        else:
            rong_st = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Dòng tiền luân chuyển chọn lọc."
            rong_col = C_REF
        
        gia_st = "NẰM TRÊN" if c > ma else "RƠI XUỐNG DƯỚI"
        gia_col = C_GREEN if c > ma else C_RED
        
        # Format HTML an toàn (không dùng chuỗi nối dài)
        html_ai_status = (
            "<div class='card' style='background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%);'>"
            "<h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ VSA & ĐỘ RỘNG (REAL-TIME)</h2>"
            "<ul style='font-size: 17px; line-height: 1.8;'>"
            f"<li><b>Động lượng Khối lượng:</b> Đạt {v/1000000:,.1f} triệu CP. Đánh giá: <b style='color:{kl_col}'>{kl_st}</b></li>"
            f"<li><b>Độ rộng thị trường (Rổ Top 200):</b> Đánh giá: <b style='color:{rong_col}'>{rong_st}</b></li>"
            f"<li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f}).</li>"
            "</ul>"
            "</div><br>"
        )
        st.markdown(html_ai_status, unsafe_allow_html=True)
        
        if ai_score >= 1: 
            sc_color = C_GREEN
            sc_title = "🟢 Kịch Bản Tích Cực (Khả năng cao nhất)"
            sc_desc = "Khối lượng gia tăng và độ rộng thị trường lan tỏa. Gia tăng tỷ trọng, tập trung giải ngân nhóm hút dòng tiền mạnh nhất trên Bản đồ nhiệt."
        elif ai_score == 0: 
            sc_color = C_REF
            sc_title = "🟡 Kịch Bản Đi Ngang / Phân Hóa (Khả năng cao nhất)"
            sc_desc = "Khối lượng suy yếu hoặc số mã giảm đang nhỉnh hơn. Hành động: Hạn chế MUA MỚI, canh nhịp kéo giá xanh để hạ bớt tỷ trọng Margin."
        else: 
            sc_color = C_RED
            sc_title = "🔴 Kịch Bản Điều Chỉnh Giảm (Khả năng cao nhất)"
            sc_desc = "Hiện tượng bán tháo rõ rệt, khối lượng bùng nổ chiều bán hoặc số mã giảm áp đảo hoàn toàn. Quản trị rủi ro tuyệt đối, đứng ngoài quan sát."

        html_scenario = (
            f"<div class='scenario-box' style='background-color: rgba(255,255,255,0.05); border-left: 5px solid {sc_color};'>"
            f"<h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>"
            f"<p style='font-size:16px;'>{sc_desc}</p>"
            "</div>"
        )
        st.markdown(html_scenario, unsafe_allow_html=True)
