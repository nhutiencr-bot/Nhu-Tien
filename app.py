import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
import re
from bs4 import BeautifulSoup

# Import vnstock an toàn
try:
    from vnstock import stock_historical_data, listing_companies
except ImportError:
    pass

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    
    .scenario-card { background-color: #1e1e2f; color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #ffaa00; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .scenario-title { color: #ffaa00; font-size: 22px; font-weight: bold; margin-bottom: 15px; }
    .prob-badge { background-color: #33334d; padding: 3px 8px; border-radius: 5px; font-weight: bold; color: #ffaa00; }
    
    div.row-widget.stRadio > div { flex-direction: column; gap: 10px; }
    div.row-widget.stRadio > div > label {
        background-color: #2a2a3c; color: white; padding: 12px 15px;
        border-radius: 8px; border: 1px solid #3f3f5a; cursor: pointer; transition: 0.3s; width: 100%; margin: 0;
    }
    div.row-widget.stRadio > div > label:hover { background-color: #3f3f5a; border-color: #ffaa00; }
    div.row-widget.stRadio > div > label[data-checked="true"] { background-color: #ffaa00; color: #1e1e2f; font-weight: bold; border: none; }
    div.row-widget.stRadio > div > label > div:first-child { display: none; }
    div.row-widget.stRadio > div > label > div:nth-child(2) { font-size: 16px; margin-left: 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. XỬ LÝ THỜI GIAN "BẤT TỬ"
# ==========================================
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)

# Lùi ngày nếu là cuối tuần để có dữ liệu
if now.weekday() == 5: 
    target_date = now - timedelta(days=1)
elif now.weekday() == 6: 
    target_date = now - timedelta(days=2)
else: 
    target_date = now

end_date = target_date.strftime('%Y-%m-%d')
start_stock = (target_date - timedelta(days=7)).strftime('%Y-%m-%d')
start_index = (target_date - timedelta(days=5)).strftime('%Y-%m-%d')
start_hist = (target_date - timedelta(days=60)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading:
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else:
        st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên: {end_date}")
    
    if st.button("🔄 Làm mới & Xóa Lỗi", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'
MAP_COLORS = [[0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED], [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF], [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]]

# ==========================================
# 3. DỮ LIỆU DỰ PHÒNG (MOCK DATA)
# ==========================================
def get_mock_market_data():
    return pd.DataFrame([
        {'Mã CK': 'VCB', 'Giá hiện tại': 92.5, '+/-': 1.2, '%': 1.3, 'Tổng KL': 2500000},
        {'Mã CK': 'FPT', 'Giá hiện tại': 135.0, '+/-': 2.5, '%': 1.8, 'Tổng KL': 4500000},
        {'Mã CK': 'HPG', 'Giá hiện tại': 29.5, '+/-': -0.3, '%': -1.0, 'Tổng KL': 15000000},
        {'Mã CK': 'SSI', 'Giá hiện tại': 36.2, '+/-': 0.8, '%': 2.2, 'Tổng KL': 8000000},
        {'Mã CK': 'VHM', 'Giá hiện tại': 42.1, '+/-': 0.0, '%': 0.0, 'Tổng KL': 5000000},
    ])

def get_mock_hist_data():
    dates = pd.date_range(end=now, periods=30, freq='B')
    df = pd.DataFrame({
        'time': dates,
        'close': [1200 + i*2 for i in range(30)],
        'volume': [500000000 + i*1000000 for i in range(30)]
    })
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['Vol_MA20'] = df['volume'].rolling(window=20).mean()
    return df.dropna()

# ==========================================
# 4. CÁC HÀM LẤY DỮ LIỆU CÓ CHỐNG GÃY
# ==========================================
@st.cache_data(ttl=120)
def get_market_data():
    try:
        tickers = listing_companies()[listing_companies()['comGroupCode'] == 'HOSE']['ticker'].head(150).tolist()
        def fetch(t):
            try:
                d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
                if len(d) < 2: return None
                curr, prev = d.iloc[-1]['close'], d.iloc[-2]['close']
                return {'Mã CK': t, 'Giá hiện tại': curr, '+/-': round(curr-prev, 2), '%': round((curr-prev)/prev*100, 2), 'Tổng KL': int(d.iloc[-1]['volume'])}
            except: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
            res = list(exe.map(fetch, tickers))
        df = pd.DataFrame([r for r in res if r])
        if df.empty: raise Exception("Rỗng")
        return df.sort_values('Tổng KL', ascending=False).head(100), False
    except:
        return get_mock_market_data(), True

@st.cache_data(ttl=60)
def get_index_contrib():
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200: 
            return pd.DataFrame(r.json()['data'])[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except: pass
    return pd.DataFrame([{'Mã CK': 'FPT', 'Điểm': 1.5}, {'Mã CK': 'VCB', 'Điểm': 1.2}, {'Mã CK': 'VIC', 'Điểm': -0.8}])

@st.cache_data(ttl=300)
def get_vnindex_history():
    try:
        df = stock_historical_data('VNINDEX', start_hist, end_date, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(window=20).mean()
            df['Vol_MA20'] = df['volume'].rolling(window=20).mean()
            return df, False
        raise Exception("Rỗng")
    except:
        return get_mock_hist_data(), True

@st.cache_data(ttl=3600)
def get_cafef_reports():
    reports = []
    try:
        url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?symbol=&DoanhNghiepID=-1&NganhCoPhieuID=-1&CongTyKienNghiID=-1&TuNgay=&DenNgay=&PageIndex=1&PageSize=30"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        blocks = re.findall(r'<li.*?>(.*?)</li>', r.text, re.DOTALL)
        for block in blocks:
            title_match = re.search(r'<a[^>]*class="doc_title"[^>]*>(.*?)</a>', block)
            if not title_match: continue
            title = title_match.group(1).strip()
            ticker = (re.search(r'([A-Z0-9]{3})', title) or re.search('', '')).group(1) or "N/A"
            link_match = re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', block)
            link = "https://s.cafef.vn" + link_match.group(1) if link_match else "N/A"
            source = (re.search(r'<span class="doc_source".*?>(.*?)</span>', block) or re.search('', '')).group(1) or "N/A"
            date_pub = (re.search(r'<span class="doc_date".*?>(.*?)</span>', block) or re.search('', '')).group(1) or "N/A"
            action = (re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN|TÍCH LŨY)', title, re.IGNORECASE) or re.search('', '')).group(1) or "ĐÁNH GIÁ"
            target = (re.search(r'mục tiêu.*?([\d,\.]+)', title, re.IGNORECASE) or re.search('', '')).group(1) or "N/A"
            if link != "N/A": reports.append({"Ngày": date_pub.strip(), "Mã CK": ticker, "CTCK": source.strip(), "Khuyến nghị": action.upper(), "Giá mục tiêu": target, "Tiêu đề Báo cáo": title, "Link PDF": link})
    except: pass
    return pd.DataFrame(reports)

# ==========================================
# 5. XUẤT GIAO DIỆN CHÍNH
# ==========================================
with st.spinner("Đang tải hệ thống..."):
    df_100, is_mock_market = get_market_data()
    df_hist, is_mock_hist = get_vnindex_history()

if is_mock_market or is_mock_hist:
    st.error("⚠️ **Hệ thống đang dùng Dữ liệu Mô phỏng.** Có thể do ngoài giờ hành chính hoặc Streamlit bị chặn IP. Hãy tải code về chạy trên máy tính (Local) để lấy dữ liệu thực.")

t1, t2, t3, t4, t5 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top Cổ phiếu", "📝 Khuyến Nghị CTCK", "🔮 Chiến lược Giao dịch"])

with t1:
    try:
        if not df_hist.empty and len(df_hist) >= 2:
            cur, ref = df_hist.iloc[-1]['close'], df_hist.iloc[-2]['close']
            st.metric(f"Điểm số VN-INDEX", f"{cur:,.2f}", f"{cur-ref:+,.2f} ({((cur-ref)/ref*100):+,.2f}%)")
            st.divider()
    except: st.warning("Đang kết nối lấy điểm số VN-INDEX...")

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
                
                # Đã sửa lỗi đứt dòng cập nhật Layout
                fig.update_layout(
                    height=380, 
                    margin=dict(l=10, r=10, t=10, b=10), 
                    legend=dict(orientation="h", y=1.1), 
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Dùng dữ liệu mô phỏng, chưa có biểu đồ thanh khoản intraday.")
        except: st.info("Dùng dữ liệu mô phỏng, chưa có biểu đồ thanh khoản intraday.")
            
    with c2:
        st.markdown("#### 🎯 Tác động tới VN-INDEX")
        try:
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([df_c[df_c['Điểm']>0].nlargest(10, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(10, 'Điểm')]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b = go.Figure(go.Bar(
                    x=df_res['Mã CK'], 
                    y=df_res['Điểm'], 
                    marker_color=b_cols, 
                    text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"), 
                    textposition='outside'
                ))
                fig_b.update_layout(
                    height=380, 
                    margin=dict(l=10, r=10, t=10, b=10), 
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_b, use_container_width=True)
        except: st.info("Biểu đồ tác động đang tải...")

with t2:
    if not df_100.empty:
        fig_m = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7])
        fig_m.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", customdata=df_100[['%', 'Tổng KL']])
        fig_m.update_layout(height=650, margin=dict(t=10,l=0,r=0,b=0))
        st.plotly_chart(fig_m, use_container_width=True)

with t3:
    if not df_100.empty:
        def style_v(v): 
            if pd.isna(v): return ''
            return f'color: {C_CEIL if v>=6.8 else C_FLOOR if v<=-6.8 else C_GREEN if v>0 else C_RED if v<0 else C_REF}; font-weight: bold;'
        st.dataframe(df_100.style.format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_v, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)

with t4:
    st.markdown("### 📝 Tổng hợp Báo Cáo Phân Tích (Nguồn: CafeF)")
    df_reports = get_cafef_reports()
    if not df_reports.empty:
        if not df_100.empty:
            df_reports = pd.merge(df_reports, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')
            cols = ['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']
            # Cắt bớt cột nếu không tìm thấy giá (để chống lỗi)
            df_reports = df_reports[[c for c in cols if c in df_reports.columns]]
            
        def style_act(val):
            v = str(val).upper()
            if any(x in v for x in ['MUA', 'KHẢ QUAN', 'TÍCH LŨY']): return f'color: {C_GREEN}; font-weight: bold; background-color: rgba(0, 230, 118, 0.1);'
            elif any(x in v for x in ['BÁN', 'KÉM']): return f'color: {C_RED}; font-weight: bold; background-color: rgba(255, 77, 77, 0.1);'
            return f'color: {C_REF}; font-weight: bold;'
            
        st.dataframe(
            df_reports.style.map(style_act, subset=['Khuyến nghị']).format({'Giá hiện tại': '{:,.2f}'}), 
            column_config={"Link PDF": st.column_config.LinkColumn("Tài liệu", display_text="📥 Tải PDF")}, 
            use_container_width=True, hide_index=True, height=600
        )
    else: st.info("Không có dữ liệu báo cáo.")

# ==========================================
# TAB 5: KỊCH BẢN THỊ TRƯỜNG TỰ ĐỘNG CHẤM ĐIỂM
# ==========================================
with t5:
    col_content, col_menu = st.columns([7, 3])
    
    with col_menu:
        st.markdown("<h4 style='color: white;'>📑 Menu Phân Tích</h4>", unsafe_allow_html=True)
        tab5_option = st.radio(
            "Chọn chức năng:", 
            ["🔮 Kịch bản What-if", "📈 Xu hướng Giá", "📊 Xu hướng Khối lượng", "⚖️ Cung - Cầu"], 
            label_visibility="collapsed"
        )

    with col_content:
        if df_hist.empty or df_100.empty:
            st.warning("Đang kết nối dữ liệu để phân tích Kịch bản...")
        else:
            cur_close = df_hist.iloc[-1]['close']
            ma20 = df_hist.iloc[-1]['MA20']
            cur_vol = df_hist.iloc[-1]['volume']
            vol_ma20 = df_hist.iloc[-1]['Vol_MA20']
            
            advances = len(df_100[df_100['%'] > 0])
            declines = len(df_100[df_100['%'] < 0])

            # THUẬT TOÁN CHẤM ĐIỂM (SCORE: 0 -> 3)
            score = 0
            if cur_close > ma20: score += 1
            if cur_vol > vol_ma20: score += 1
            if advances > declines: score += 1

            if score == 3:
                status_text, prob_up, prob_mid, prob_down = "RẤT TÍCH CỰC", "60 - 70%", "20 - 30%", "0 - 10%"
                status_color = C_CEIL
            elif score == 2:
                status_text, prob_up, prob_mid, prob_down = "TÍCH CỰC", "40 - 50%", "30 - 40%", "10 - 20%"
                status_color = C_GREEN
            elif score == 1:
                status_text, prob_up, prob_mid, prob_down = "THẬN TRỌNG", "10 - 20%", "30 - 40%", "40 - 50%"
                status_color = C_REF
            else:
                status_text, prob_up, prob_mid, prob_down = "TIÊU CỰC", "0 - 10%", "20 - 30%", "60 - 70%"
                status_color = C_RED

            if tab5_option == "🔮 Kịch bản What-if":
                st.markdown(f"""
                <div class="scenario-card">
                    <div class="scenario-title">Dự báo chiến lược giao dịch (Real-time AI Scoring)</div>
                    <p>Hệ thống tự động phân tích 3 biến số (Giá vs MA20, Khối lượng, Cung Cầu) và cho ra điểm số trạng thái: <b style='color:{status_color}; font-size:18px;'>{status_text} ({score}/3 Điểm Tích Cực)</b>.</p>
                    <hr style="border-color: #3f3f5a;">
                    <div class="scenario-item"><p>🟢 <b>Kịch bản Tích cực</b> (Tiếp diễn đà tăng) - Xác suất <span class="prob-badge">{prob_up}</span></p><p>Dòng tiền lan tỏa, VN-INDEX hướng lên các mốc kháng cự mới.</p></div>
                    <hr style="border-color: #3f3f5a;">
                    <div class="scenario-item"><p>🟡 <b>Kịch bản Trung tính</b> (Sideway tích lũy) - Xác suất <span class="prob-badge">{prob_mid}</span></p><p>Giá dao động đi ngang biên độ hẹp, dòng tiền phân hóa chọn lọc.</p></div>
                    <hr style="border-color: #3f3f5a;">
                    <div class="scenario-item"><p>🔴 <b>Kịch bản Tiêu cực</b> (Áp lực điều chỉnh) - Xác suất <span class="prob-badge">{prob_down}</span></p><p>Phe bán chiếm ưu thế, thị trường có nguy cơ lùi về kiểm định các mốc hỗ trợ sâu hơn.</p></div>
                </div>
                """, unsafe_allow_html=True)

            elif tab5_option == "📈 Xu hướng Giá":
                st.markdown("### Phân tích Xu hướng Giá VN-INDEX")
                st.info(f"VN-INDEX đang ở mức **{cur_close:,.2f}**, {'NẰM TRÊN' if cur_close > ma20 else 'NẰM DƯỚI'} đường trung bình 20 ngày (MA20: {ma20:,.2f}).")
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['close'], name='VN-INDEX', line=dict(color='white', width=2)))
                fig_p.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['MA20'], name='MA20', line=dict(color=C_GREEN, width=1, dash='dash')))
                
                # Đã sửa lỗi đứt dòng cập nhật Layout
                fig_p.update_layout(
                    height=400, 
                    plot_bgcolor='#1e1e2f', 
                    paper_bgcolor='#1e1e2f', 
                    font_color='white'
                )
                st.plotly_chart(fig_p, use_container_width=True)

            elif tab5_option == "📊 Xu hướng Khối lượng":
                st.markdown("### Phân tích Khối lượng Giao dịch")
                st.info(f"Khối lượng phiên gần nhất: **{cur_vol:,.0f}** CP, {'VƯỢT' if cur_vol > vol_ma20 else 'THẤP HƠN'} mức trung bình 20 phiên ({vol_ma20:,.0f}).")
                fig_v = go.Figure()
                c_vol = [C_GREEN if df_hist['close'].iloc[i] > df_hist['close'].iloc[i-1] else C_RED for i in range(1, len(df_hist))]
                c_vol.insert(0, C_GREEN)
                fig_v.add_trace(go.Bar(x=df_hist['time'], y=df_hist['volume'], name='Khối lượng', marker_color=c_vol))
                fig_v.add_trace(go.Scatter(x=df_hist['time'], y=df_hist['Vol_MA20'], name='Trung bình 20 phiên', line=dict(color='#ffaa00', width=2)))
                
                # Đã sửa lỗi đứt dòng cập nhật Layout
                fig_v.update_layout(
                    height=400, 
                    plot_bgcolor='#1e1e2f', 
                    paper_bgcolor='#1e1e2f', 
                    font_color='white'
                )
                st.plotly_chart(fig_v, use_container_width=True)

            elif tab5_option == "⚖️ Cung - Cầu":
                st.markdown("### Đánh giá Cung - Cầu (Rổ Top 100)")
                st.markdown(f"""
                <div class="scenario-card" style="text-align: center;">
                    <h4>Độ rộng thị trường</h4>
                    <h1 style='color: {C_GREEN}; display: inline;'>{advances} Mã Tăng</h1> <h1 style='color: gray; display: inline;'> | </h1> <h1 style='color: {C_RED}; display: inline;'>{declines} Mã Giảm</h1>
                    <p style="margin-top: 15px; font-size: 18px;">Dòng tiền đang <b>{'Kéo giá lên (Cầu > Cung)' if advances > declines else 'Chốt lời/Bán tháo (Cung > Cầu)'}</b> rõ rệt.</p>
                </div>
                """, unsafe_allow_html=True)
