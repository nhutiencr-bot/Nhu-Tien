import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
import requests
import urllib.parse
import re
import concurrent.futures

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="AI & Khuyến Nghị", page_icon="🔮", layout="wide")

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

st.title("🔮 CẬP NHẬT KHUYẾN NGHỊ & PHÂN TÍCH AI (VSA)")

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & MÀU SẮC
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_date_stock = (now - timedelta(days=7)).strftime('%Y-%m-%d')
start_hist_ma = (now - timedelta(days=60)).strftime('%Y-%m-%d')

C_GREEN, C_REF, C_RED = '#00e676', '#f5b041', '#ff4d4d'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU ĐỘC LẬP
# ==========================================
def fetch_url_with_proxies(target_url, is_json=True):
    encoded = urllib.parse.quote(target_url, safe='')
    urls = [target_url, f"https://api.codetabs.com/v1/proxy?quest={encoded}", f"https://api.allorigins.win/raw?url={encoded}"]
    for url in urls:
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

@st.cache_data(ttl=300)
def get_market_breadth():
    try:
        df_list = listing_companies()
        tickers = df_list[(df_list['comGroupCode'] == 'HOSE') & (df_list['ticker'].str.len() == 3)]['ticker'].tolist()
        
        def fetch_ticker(ticker):
            try:
                df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
                if len(df) >= 2:
                    return {'Mã CK': ticker, '%': (df.iloc[-1]['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] * 100, 'Tổng KL': df.iloc[-1]['volume']}
            except: return None

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            for res in executor.map(fetch_ticker, tickers):
                if res and res['Tổng KL'] > 0: results.append(res)
                    
        df = pd.DataFrame(results)
        if not df.empty: return df.sort_values(by='Tổng KL', ascending=False).head(150)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_cafef_reports():
    url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    html = fetch_url_with_proxies(url, is_json=False)
    res = []
    
    # Chia nhỏ Regex để chống đứt gãy code
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
                if any(w in t_up for w in ["MUA", "BUY", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): action = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): action = "NẮM GIỮ"
                
                res.append({
                    "Ngày": d_m.group(1).strip() if d_m else "", 
                    "Mã CK": ticker, 
                    "Khuyến nghị": action, 
                    "CTCK": s_m.group(1).strip() if s_m else "", 
                    "Nội dung tóm tắt": title, 
                    "Link Báo Cáo": link
                })
    return pd.DataFrame(res)

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang thu thập dữ liệu AI & Khuyến nghị..."):
    df_reports = get_cafef_reports()
    df_ma = get_vnindex_daily_ma()
    df_market = get_market_breadth()
    df_c = get_index_contrib()

t1, t2 = st.tabs(["📝 Báo cáo Khuyến nghị (CafeF)", "🤖 AI Nhận định (Chuẩn VSA)"])

# TAB 1: KHUYẾN NGHỊ CAFEF
with t1:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Báo Cáo Phân Tích Mới Nhất")
        st.dataframe(
            df_reports.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), 
            column_config={"Link Báo Cáo": st.column_config.LinkColumn("Tải PDF")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else:
        st.warning("Hệ thống đang quét báo cáo. Vui lòng bấm F5 để thử lại do máy chủ CafeF phản hồi chậm.")

# TAB 2: AI VSA VÀ TÁC ĐỘNG CHỈ SỐ
with t2:
    col1, col2 = st.columns([1.5, 1])
    
    with col2:
        st.markdown("#### 🎯 Top Cổ Phiếu Ảnh Hưởng VN-INDEX")
        st.caption("*(Dựa trên Số lượng CP Lưu hành & Vốn hóa)*")
        if not df_c.empty:
            df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
            fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=[C_GREEN if v > 0 else C_RED for v in df_res['Điểm']], text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
            fig_b.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=450, plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_b, use_container_width=True)
        else:
            st.info("Đang xử lý dữ liệu tác động...")

    with col1:
        if not df_ma.empty and not df_market.empty:
            c, ma, v, v_ma = df_ma.iloc[-1]['close'], df_ma.iloc[-1]['MA20'], df_ma.iloc[-1]['volume'], df_ma.iloc[-1]['V_MA20']
            adv, dec = len(df_market[df_market['%'] > 0]), len(df_market[df_market['%'] < 0])
            
            ai_score = 0
            vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
            
            # Đánh giá Khối lượng
            if vol_ratio >= 120:
                kl_st, kl_col = f"BÙNG NỔ ({vol_ratio:.1f}% MA20). Khối lượng vượt xa mức trung bình 20 phiên ({v_ma/1000000:,.1f} Tr CP). Dòng tiền vào mạnh mẽ.", C_GREEN
                ai_score += 1 if c > ma else -1
            elif vol_ratio >= 80:
                kl_st, kl_col = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20). Khối lượng duy trì quanh mức trung bình tự nhiên.", C_GREEN
                ai_score += 1
            else:
                kl_st, kl_col = f"SUY YẾU ({vol_ratio:.1f}% MA20). Lực cầu còn dè dặt, dòng tiền lớn chưa tham gia.", C_RED
                
            # Đánh giá Độ rộng
            if adv > dec * 1.5:
                rong_st, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm). Sắc xanh áp đảo.", C_GREEN
                ai_score += 1
            elif dec > adv * 1.5:
                rong_st, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm). Dấu hiệu bán diện rộng, 'Xanh vỏ đỏ lòng'.", C_RED
                ai_score -= 1
            else:
                rong_st, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Sự luân chuyển dòng tiền.", C_REF
            
            gia_st = "NẰM TRÊN" if c > ma else "RƠI XUỐNG DƯỚI"
            gia_col = C_GREEN if c > ma else C_RED
            
            html_ai_status = (
                "<div class='card'>"
                "<h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ TRẠNG THÁI (REAL-TIME)</h2>"
                "<ul style='font-size: 16px; line-height: 1.8;'>"
                f"<li><b>Động lượng Khối lượng:</b> Đạt {v/1000000:,.1f} Tr CP. <b style='color:{kl_col}'>{kl_st}</b></li>"
                f"<li><b>Độ rộng thị trường:</b> Đánh giá: <b style='color:{rong_col}'>{rong_st}</b></li>"
                f"<li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f}).</li>"
                "</ul>"
                "</div>"
            )
            st.markdown(html_ai_status, unsafe_allow_html=True)
            
            if ai_score >= 1: 
                sc_color, sc_title, sc_desc = C_GREEN, "🟢 Kịch Bản Tích Cực", "Khối lượng gia tăng và độ rộng thị trường lan tỏa. Gia tăng tỷ trọng cổ phiếu, mở mua mới mã có nền giá tốt."
            elif ai_score == 0: 
                sc_color, sc_title, sc_desc = C_REF, "🟡 Kịch Bản Đi Ngang", "Khối lượng suy yếu hoặc số mã giảm đang nhỉnh hơn. Hạn chế MUA MỚI, giữ tỷ trọng cân bằng. Canh hạ margin khi kéo xanh."
            else: 
                sc_color, sc_title, sc_desc = C_RED, "🔴 Kịch Bản Điều Chỉnh Giảm", "Hiện tượng bán tháo rõ rệt. Quản trị rủi ro tuyệt đối, hạ tỷ trọng Margin, đứng ngoài quan sát."

            st.markdown(
                f"<div class='scenario-box' style='border-left: 5px solid {sc_color};'>"
                f"<h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>"
                f"<p style='font-size:16px;'>{sc_desc}</p>"
                "</div>", unsafe_allow_html=True
            )
        else:
            st.info("Hệ thống AI đang chờ thu thập đủ dữ liệu thị trường...")
