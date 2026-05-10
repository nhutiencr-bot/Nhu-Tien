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

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
    .scenario-item { margin-bottom: 15px; line-height: 1.6; }
    .prob-badge { background-color: #33334d; padding: 3px 8px; border-radius: 5px; font-weight: bold; color: #ffaa00; }
    .right-menu-btn { background-color: #2a2a3c; color: white; padding: 10px 15px; border-radius: 8px; margin-bottom: 10px; text-align: left; border: 1px solid #3f3f5a; cursor: pointer; transition: 0.3s; }
    .right-menu-btn:hover { background-color: #3f3f5a; border-color: #ffaa00; }
    .right-menu-active { background-color: #ffaa00; color: #1e1e2f; font-weight: bold; border: none; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THIẾT LẬP THỜI GIAN
# ==========================================
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

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# 3. CÁC HÀM LẤY DỮ LIỆU THỊ TRƯỜNG (Đã Tối Ưu RAM)
# ==========================================
@st.cache_data(ttl=86400)
def get_hose_tickers():
    try:
        df = listing_companies()
        # Lấy Top 150 mã vốn hóa lớn/thanh khoản cao thay vì quét 400 mã để tránh sập RAM
        return df[df['comGroupCode'] == 'HOSE']['ticker'].head(150).tolist()
    except: return ['VCB', 'VHM', 'VIC', 'FPT', 'HPG', 'SSI', 'VND', 'VIX'] # Fallback an toàn

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if len(d) < 2: return None
            curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
            return {'Mã CK': t, 'Giá hiện tại': curr, '+/-': round(curr-prev, 2), '%': round((curr-prev)/prev*100, 2), 'Tổng KL': int(d.iloc[-1]['volume'])}
        except: return None
    
    # Giảm max_workers xuống 8 để máy chủ Streamlit không bị quá tải (Memory Limit)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
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

@st.cache_data(ttl=3600)
def get_cafef_reports():
    reports = []
    try:
        url = "https://cafef.vn/du-lieu/phan-tich-bao-cao.chn"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        
        table = soup.find('table', {'id': 'tblGridData'})
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows[:20]: # Lấy 20 báo cáo để web mượt
                cols = row.find_all('td')
                if len(cols) >= 5:
                    date_pub, ticker, source = cols[0].text.strip(), cols[1].text.strip(), cols[2].text.strip()
                    title_tag = cols[3].find('a')
                    title = title_tag.text.strip() if title_tag else cols[3].text.strip()
                    
                    link_pdf = "https://cafef.vn" + title_tag['href'] if title_tag and title_tag.has_attr('href') else "N/A"
                    
                    action_match = re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN|TÍCH LŨY|TRUNG LẬP)', title, re.IGNORECASE)
                    action = action_match.group(1).upper() if action_match else "ĐÁNH GIÁ"
                    price_match = re.search(r'mục tiêu.*?([\d,\.]+)', title, re.IGNORECASE)
                    target_price = price_match.group(1) if price_match else "N/A"
                    
                    if ticker:
                        reports.append({"Ngày": date_pub, "Mã CK": ticker, "CTCK": source, "Khuyến nghị": action, "Giá mục tiêu": target_price, "Tiêu đề Báo cáo": title, "Link PDF": link_pdf})
    except: pass
    return pd.DataFrame(reports)

# ==========================================
# 4. HIỂN THỊ GIAO DIỆN CÁC TABS
# ==========================================
try:
    with st.spinner("Đang kết nối dữ liệu an toàn..."):
        df_100 = get_market_data()

    t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Khuyến Nghị CTCK", "🔮 Kịch bản Thị trường"])

    with t1:
        try:
            df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
            if not df_daily.empty and len(df_daily) >= 2:
                cur, ref = df_daily.iloc[-1]['close'], df_daily.iloc[-2]['close']
                st.metric(f"Điểm số VN-INDEX", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
                st.divider()
        except: st.warning("Đang kết nối để lấy điểm số VN-INDEX...")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌊 Thanh khoản")
            try:
                df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
                if not df_idx.empty:
                    dates = pd.to_datetime(df_idx['time']).dt.date.unique()
                    df_t = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-1]].copy()
                    df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                    fig = go.Figure()
                    
                    if len(dates) >= 2:
                        df_y = df_idx[pd.to_datetime(df_idx['time']).dt.date == dates[-2]].copy()
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
                    df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                    b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                    fig_b = go.Figure(go.Bar(x=df_res['Mã CK'], y=df_res['Điểm'], marker_color=b_cols, text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                    fig_b.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_b, use_container_width=True)
                else: st.info("☕ Biểu đồ tác động đang được cập nhật.")
            except: st.info("☕ Biểu đồ tác động đang được cập nhật.")

    with t2:
        if not df_100.empty:
            fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
            fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
            fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0))
            st.plotly_chart(fig_m, use_container_width=True)

    with t3:
        if not df_100.empty:
            def style_v(v):
                if v >= 6.8: return f'color: {C_CEIL}; font-weight: bold;'
                elif v <= -6.8: return f'color: {C_FLOOR}; font-weight: bold;'
                elif v > 0: return f'color: {C_GREEN}; font-weight: bold;'
                elif v == 0: return f'color: {C_REF}; font-weight: bold;'
                elif v > -3: return f'color: {C_RED}; font-weight: bold;'
                else: return f'color: {C_DRED}; font-weight: bold;'
            st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

    with t4:
        st.markdown("### 📝 Tổng hợp Báo Cáo Phân Tích (Nguồn: CafeF)")
        df_reports = get_cafef_reports()
        if not df_reports.empty:
            if not df_100.empty:
                df_reports = pd.merge(df_reports, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')
                df_reports = df_reports[['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']]
            def style_action(val):
                v = str(val).upper()
                if any(x in v for x in ['MUA', 'KHẢ QUAN', 'TÍCH LŨY']): return f'color: {C_GREEN}; font-weight: bold; background-color: rgba(0, 230, 118, 0.1);'
                elif any(x in v for x in ['BÁN', 'KÉM']): return f'color: {C_RED}; font-weight: bold; background-color: rgba(255, 77, 77, 0.1);'
                return f'color: {C_REF}; font-weight: bold;'
            st.dataframe(df_reports.style.map(style_action, subset=['Khuyến nghị']).format({'Giá hiện tại': '{:,.2f}'}), column_config={"Ngày": st.column_config.TextColumn("Ngày", width="small"), "CTCK": st.column_config.TextColumn("CTCK", width="small"), "Tiêu đề Báo cáo": st.column_config.TextColumn("Nội dung báo cáo", width="large"), "Link PDF": st.column_config.LinkColumn("Tài liệu", display_text="📥 Xem báo cáo"), "Giá mục tiêu": st.column_config.TextColumn("Mục tiêu")}, use_container_width=True, hide_index=True, height=600)
        else: st.warning("⚠️ Tạm thời không lấy được dữ liệu báo cáo.")

    with t5:
        col_content, col_menu = st.columns([7, 3])
        with col_content:
            st.markdown("""
            <div class="scenario-card">
                <div class="scenario-title">Kịch Bản "What-if" trước phiên</div>
                <p>Chúng ta cùng thống nhất <b>3 kịch bản chính</b>, với xác suất đặt cho khung trung hạn (10 - 20 phiên).</p>
                <hr style="border-color: #3f3f5a;">
                <div class="scenario-item"><p>🔴 <b>Kịch bản Tiêu cực</b> (Phá hỗ trợ, tiếp tục giảm) - Xác suất <span class="prob-badge">45 - 55%</span></p><p>Giá phá vỡ và đóng cửa dưới vùng hỗ trợ mạnh <b>1,245 - 1,250</b>.</p><p><b>Dẫn chứng:</b> Breadth percentile duy trì dưới 20%, số mã chạm đáy 52 tuần tăng, và khối lượng trên nhóm giảm bùng nổ.</p></div>
                <hr style="border-color: #3f3f5a;">
                <div class="scenario-item"><p>🟡 <b>Kịch bản Trung tính</b> (Sideway tích lũy trong biên độ hẹp) - Xác suất <span class="prob-badge">30 - 40%</span></p><p>Giá dao động trong khoảng <b>1,250 - 1,280</b>, không thể phá vỡ hỗ trợ.</p><p><b>Dẫn chứng:</b> Tín hiệu hưng phấn thoát vùng siêu bán nhưng không mạnh.</p></div>
                <hr style="border-color: #3f3f5a;">
                <div class="scenario-item"><p>🟢 <b>Kịch bản Tích cực</b> (Phục hồi kỹ thuật) - Xác suất <span class="prob-badge">15 - 25%</span></p><p>Giá bật tăng mạnh từ vùng <b>1,245 - 1,250</b> và giữ được trên vùng <b>1,280 - 1,290</b>.</p><p><b>Dẫn chứng:</b> Dòng tiền lớn quay lại nhóm VN30, khối ngoại ngừng bán ròng.</p></div>
            </div>
            """, unsafe_allow_html=True)
        with col_menu:
            st.markdown("""<div style="padding-top: 10px;"><div class="right-menu-btn">📈 Xu hướng Giá</div><div class="right-menu-btn">📊 Xu hướng Khối lượng</div><div class="right-menu-btn">⚖️ Cung - Cầu</div><div class="right-menu-btn right-menu-active">🔮 Kịch bản What-if</div></div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Đã xảy ra lỗi hệ thống: {e}. Vui lòng Reboot lại ứng dụng.")
