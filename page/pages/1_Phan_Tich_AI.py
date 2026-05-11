import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import urllib.parse
import requests
import re
import concurrent.futures

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & CSS
# ==========================================
st.set_page_config(page_title="Phân Tích Chuyên Sâu", page_icon="🔮", layout="wide")
st.title("🔮 CẬP NHẬT KHUYẾN NGHỊ & AI VSA")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 17px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .card { background-color: #1e1e2f; padding: 25px; border-radius: 10px; border-left: 5px solid #ffaa00; color: white; margin-top: 10px; }
    .scenario-box { background-color: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN & MÀU SẮC
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_hist_ma = (current_time - timedelta(days=60)).strftime('%Y-%m-%d')

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_LRED, C_FLOOR = '#b30000', '#ff4d4d', '#00e5ff'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU
# ==========================================
# Tái sử dụng hàm quét Top 100 của bạn để đồng bộ dữ liệu
@st.cache_data(ttl=86400)
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=300)
def get_dynamic_top_100():
    sector_dict = get_company_sectors()
    tickers = list(sector_dict.keys())
    
    def fetch_ticker(ticker):
        try:
            df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
            if len(df) >= 2:
                close_today = df.iloc[-1]['close']
                close_yest = df.iloc[-2]['close']
                return {
                    'Mã CK': ticker,
                    '%': round(((close_today - close_yest) / close_yest) * 100, 2),
                    'Tổng KL': int(df.iloc[-1]['volume'])
                }
        except: return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0: results.append(res)
                
    df_market = pd.DataFrame(results)
    if not df_market.empty: return df_market.sort_values(by='Tổng KL', ascending=False).head(100)
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

@st.cache_data(ttl=1800)
def get_cafef_reports():
    url_target = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    encoded = urllib.parse.quote(url_target, safe='')
    urls = [url_target, f"https://api.codetabs.com/v1/proxy?quest={encoded}", f"https://api.allorigins.win/raw?url={encoded}"]
    
    html = ""
    for u in urls:
        try:
            res = requests.get(u, headers=HEADERS, timeout=8)
            if res.status_code == 200 and "<li" in res.text:
                html = res.text
                break
        except: continue

    res_list = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m, s_m, d_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b), re.search(r'class="doc_source"[^>]*>(.*?)</span>', b), re.search(r'class="doc_date"[^>]*>(.*?)</span>', b)
            
            if t_m and l_m:
                title = t_m.group(1).strip()
                link = "https://s.cafef.vn" + l_m.group(1)
                tk_match = re.search(r'\b([A-Z0-9]{3})\b', title)
                ticker = tk_match.group(1) if tk_match else ""
                
                action = "ĐÁNH GIÁ"
                t_up = title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): action = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): action = "NẮM GIỮ"
                
                res_list.append({
                    "Ngày": d_m.group(1).strip() if d_m else "", 
                    "Mã CK": ticker, 
                    "Khuyến nghị": action, 
                    "CTCK": s_m.group(1).strip() if s_m else "", 
                    "Nội dung Báo cáo": title, 
                    "Link Báo Cáo": link
                })
    return pd.DataFrame(res_list)

# ==========================================
# 4. GIAO DIỆN TABS
# ==========================================
with st.spinner("Đang tổng hợp Khuyến nghị và Khởi động AI..."):
    df_top100 = get_dynamic_top_100()
    df_ma = get_vnindex_daily_ma()
    df_reports = get_cafef_reports()

tab1, tab2 = st.tabs(["📝 Cập nhật Khuyến nghị", "🔮 Phân Tích AI (VSA)"])

# TAB 1: KHUYẾN NGHỊ CAFEF
with tab1:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị Phân Tích (CafeF)")
        st.dataframe(
            df_reports.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), 
            column_config={"Link Báo Cáo": st.column_config.LinkColumn("Bấm để xem PDF")}, 
            hide_index=True, use_container_width=True, height=600
        )
    else:
        st.warning("Đang quét báo cáo Khuyến nghị từ các CTCK...")

# TAB 2: AI VSA CHUYÊN SÂU
with tab2:
    if not df_ma.empty and not df_top100.empty:
        c, ma, v, v_ma = df_ma.iloc[-1]['close'], df_ma.iloc[-1]['MA20'], df_ma.iloc[-1]['volume'], df_ma.iloc[-1]['V_MA20']
        adv, dec = len(df_top100[df_top100['%'] > 0]), len(df_top100[df_top100['%'] < 0])
        
        ai_score = 0
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0
        
        # Đánh giá Khối lượng
        if vol_ratio >= 120:
            kl_st, kl_col = f"BÙNG NỔ ({vol_ratio:.1f}% MA20). Khối lượng vượt xa mức trung bình 20 phiên ({v_ma/1000000:,.1f} Tr CP).", C_CEIL
            ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80:
            kl_st, kl_col = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20). Khối lượng duy trì quanh mức trung bình tự nhiên.", C_GREEN
            ai_score += 1
        else:
            kl_st, kl_col = f"SUY YẾU ({vol_ratio:.1f}% MA20). Dòng tiền lớn đang đứng ngoài, lực cầu cạn kiệt.", C_RED
            
        # Đánh giá Độ rộng (Hiện tượng Xanh vỏ đỏ lòng)
        if adv > dec * 1.5:
            rong_st, rong_col = f"LAN TỎA TÍCH CỰC (Có {adv} mã Tăng áp đảo {dec} mã Giảm). Dòng tiền mua lan rộng.", C_GREEN
            ai_score += 1
        elif dec > adv * 1.5:
            rong_st, rong_col = f"CẢNH BÁO RỦI RO (Chỉ có {adv} mã Tăng nhưng tới {dec} mã Giảm). Hiện tượng 'Xanh vỏ, đỏ lòng'.", C_RED
            ai_score -= 1
        else:
            rong_st, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Dòng tiền luân chuyển chọn lọc.", C_REF
        
        gia_st = "NẰM TRÊN" if c > ma else "RƠI XUỐNG DƯỚI"
        gia_col = C_GREEN if c > ma else C_RED
        
        html_ai_status = (
            "<div class='card'>"
            "<h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ VSA & ĐỘ RỘNG</h2>"
            "<ul style='font-size: 17px; line-height: 1.8;'>"
            f"<li><b>Động lượng Khối lượng:</b> Đạt {v/1000000:,.1f} triệu CP. Đánh giá: <b style='color:{kl_col}'>{kl_st}</b></li>"
            f"<li><b>Độ rộng thị trường (Rổ 100 mã dẫn dắt):</b> Đánh giá: <b style='color:{rong_col}'>{rong_st}</b></li>"
            f"<li><b>Hành động Giá:</b> VN-INDEX đang <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f}).</li>"
            "</ul>"
            "</div><br>"
        )
        st.markdown(html_ai_status, unsafe_allow_html=True)
        
        if ai_score >= 1: 
            sc_color, sc_title, sc_desc = C_GREEN, "🟢 Kịch Bản Tích Cực (Khả năng cao nhất)", "Khối lượng gia tăng và độ rộng thị trường lan tỏa. Gia tăng tỷ trọng, tập trung giải ngân nhóm hút dòng tiền mạnh nhất."
        elif ai_score == 0: 
            sc_color, sc_title, sc_desc = C_REF, "🟡 Kịch Bản Đi Ngang / Phân Hóa (Khả năng cao nhất)", "Khối lượng suy yếu hoặc số mã giảm đang nhỉnh hơn. Hành động: Hạn chế MUA MỚI, canh nhịp kéo giá xanh để hạ bớt tỷ trọng Margin."
        else: 
            sc_color, sc_title, sc_desc = C_RED, "🔴 Kịch Bản Điều Chỉnh Giảm (Khả năng cao nhất)", "Hiện tượng bán tháo rõ rệt, khối lượng bùng nổ chiều bán hoặc số mã giảm áp đảo hoàn toàn. Quản trị rủi ro tuyệt đối, đứng ngoài quan sát."

        html_scenario = (
            f"<div class='scenario-box' style='border-left: 5px solid {sc_color};'>"
            f"<h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>"
            f"<p style='font-size:16px;'>{sc_desc}</p>"
            "</div>"
        )
        st.markdown(html_scenario, unsafe_allow_html=True)
    else:
        st.info("Hệ thống AI đang chờ thu thập đủ dữ liệu thị trường...")
