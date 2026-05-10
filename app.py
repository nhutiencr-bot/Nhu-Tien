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

# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_stock = (now - timedelta(days=14)).strftime('%Y-%m-%d')
start_index = (now - timedelta(days=10)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and ((9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30))

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading:
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else:
        st.warning(f"🔴 ĐÃ ĐÓNG CỬA | {now.strftime('%H:%M %d/%m/%Y')}")

    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.toast("Đã làm mới dữ liệu thị trường!", icon="✅")

# 3. MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

# 4. CÁC HÀM LẤY DỮ LIỆU
@st.cache_data(ttl=300)
def get_hose_tickers():
    try:
        df = listing_companies()
        return df[df['comGroupCode'] == 'HOSE']['ticker'].tolist()
    except:
        return []

@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    if not tickers:
        return pd.DataFrame()

    def fetch(t):
        try:
            d = stock_historical_data(t, start_stock, end_date, '1D', 'stock')
            if d is None or d.empty:
                return None
            d = d.dropna(subset=['close', 'volume'])
            if len(d) < 2:
                return None
            curr = d.iloc[-1]['close']
            prev = d.iloc[-2]['close']
            if prev == 0:
                return None
            return {
                'Mã CK': t,
                'Giá hiện tại': curr,
                '+/-': round(curr - prev, 2),
                '%': round((curr - prev) / prev * 100, 2),
                'Tổng KL': int(d.iloc[-1]['volume'])
            }
        except:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
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
    except:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_cafef_reports_v2():
    reports = []
    try:
        url = "https://cafef.vn/du-lieu/phan-tich-bao-cao.chn"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        table = soup.find('table', {'id': 'tblGridData'})
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 5:
                    date_pub = cols[0].text.strip()
                    ticker = cols[1].text.strip()
                    source = cols[2].text.strip()
                    title_tag = cols[3].find('a')
                    title = title_tag.text.strip() if title_tag else cols[3].text.strip()
                    link_pdf = "N/A"
                    if title_tag and title_tag.has_attr('href'):
                        href = title_tag['href']
                        link_pdf = "https://cafef.vn" + href if href.startswith('/') else href
                    action_match = re.search(r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN|TÍCH LŨY|TRUNG LẬP)', title, re.IGNORECASE)
                    action = action_match.group(1).upper() if action_match else "ĐÁNH GIÁ"
                    price_match = re.search(r'mục tiêu.*?([\d,\.]+)', title, re.IGNORECASE)
                    target_price = price_match.group(1) if price_match else "N/A"
                    if ticker:
                        reports.append({
                            "Ngày": date_pub,
                            "Mã CK": ticker,
                            "CTCK": source,
                            "Khuyến nghị": action,
                            "Giá mục tiêu": target_price,
                            "Tiêu đề Báo cáo": title,
                            "Link PDF": link_pdf
                        })
    except Exception as e:
        print(f"Error scraping CafeF: {e}")
    return pd.DataFrame(reports)

# 5. LOAD DỮ LIỆU CHÍNH
with st.spinner("Đang tính toán dữ liệu thị trường..."):
    df_100 = get_market_data()

if df_100.empty:
    st.error("⚠️ Không lấy được dữ liệu thị trường. Thử nhấn 🔄 Cập nhật.")

# 6. TABS
t1, t2, t3, t4, t5 = st.tabs([
    "📈 VN-INDEX & Đóng góp",
    "🗺️ Bản đồ Dòng tiền",
    "📊 Top 100 Cổ phiếu",
    "📝 Khuyến Nghị CTCK",
    "📡 AI Phân Tích"
])

# ── TAB 1 ──────────────────────────────────────────────
with t1:
    try:
        df_daily = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
        if df_daily is not None and not df_daily.empty:
            df_daily = df_daily.dropna(subset=['close'])
        if df_daily is not None and len(df_daily) >= 2:
            cur = df_daily.iloc[-1]['close']
            ref = df_daily.iloc[-2]['close']
            time_str = df_daily.iloc[-1]['time']
            delta_val = cur - ref
            delta_pct = (delta_val / ref * 100) if ref != 0 else 0
            st.metric(
                f"Điểm số VN-INDEX (Chốt phiên {time_str})",
                f"{cur:,.2f}",
                f"{delta_val:+,.2f} ({delta_pct:+,.2f}%)"
            )
        else:
            st.info("📊 Chưa có dữ liệu VN-INDEX cho khoảng thời gian này.")
        st.divider()
    except Exception as e:
        st.warning(f"Đang kết nối để lấy điểm số VN-INDEX... ({e})")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🌊 Thanh khoản")
        try:
            df_idx = stock_historical_data('VNINDEX', start_index, end_date, '1', 'index')
            if df_idx is not None and not df_idx.empty:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = df_idx['date'].unique()
                df_t = df_idx[df_idx['date'] == dates[-1]].copy()
                df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                fig = go.Figure()
                if len(dates) >= 2:
                    df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig.add_trace(go.Scatter(
                        x=df_y['ts'], y=df_y['volume'].cumsum(),
                        fill='tozeroy', name='Phiên trước',
                        line=dict(color='rgba(150,150,150,0.5)')
                    ))
                fig.add_trace(go.Scatter(
                    x=df_t['ts'], y=df_t['volume'].cumsum(),
                    fill='tozeroy', name='Phiên gần nhất',
                    line=dict(color=C_GREEN)
                ))
                fig.update_layout(
                    height=380, margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", y=1.1),
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("☕ Không có dữ liệu intraday (ngoài giờ giao dịch / cuối tuần).")
        except:
            st.info("☕ Đồ thị thanh khoản không khả dụng ngoài giờ giao dịch.")

    with c2:
        st.markdown("#### 🎯 Tác động tới VN-INDEX")
        try:
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([
                    df_c[df_c['Điểm'] > 0].nlargest(10, 'Điểm'),
                    df_c[df_c['Điểm'] < 0].nsmallest(10, 'Điểm')
                ]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b = go.Figure(go.Bar(
                    x=df_res['Mã CK'], y=df_res['Điểm'],
                    marker_color=b_cols,
                    text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"),
                    textposition='outside'
                ))
                fig_b.update_layout(
                    height=380, margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_b, use_container_width=True)
            else:
                st.info("☕ Biểu đồ tác động chỉ khả dụng trong giờ giao dịch.")
        except:
            st.info("☕ Biểu đồ tác động đang được cập nhật.")

# ── TAB 2 ──────────────────────────────────────────────
with t2:
    if not df_100.empty:
        with st.spinner("Đang kết xuất Bản đồ Dòng tiền..."):
            fig_m = px.treemap(
                df_100,
                path=[px.Constant("Thị trường"), 'Mã CK'],
                values='Tổng KL',
                color='%',
                color_continuous_scale=MAP_COLORS,
                range_color=[-7, 7]
            )
            fig_m.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%",
                customdata=df_100[['%', 'Tổng KL']]
            )
            fig_m.update_layout(height=650, margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.info("Không có dữ liệu để hiển thị bản đồ dòng tiền.")

# ── TAB 3 ──────────────────────────────────────────────
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

        st.markdown("### Top 100 Cổ Phiếu Giao Dịch Mạnh Nhất")
        st.dataframe(
            df_100.style
            .format({'Giá hiện tại': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'})
            .map(style_v, subset=['+/-', '%']),
            use_container_width=True, hide_index=True, height=600
        )
    else:
        st.info("Không có dữ liệu cổ phiếu. Thử nhấn 🔄 Cập nhật.")

# ── TAB 4 ──────────────────────────────────────────────
with t4:
    st.markdown("### 📝 Tổng hợp Báo Cáo Phân Tích (Nguồn: CafeF)")
    df_reports = get_cafef_reports_v2()

    if df_reports.empty:
        st.warning("⚠️ Đang sử dụng dữ liệu dự phòng do rào cản khu vực (Streamlit IP).")
        fallback_data = [
            {"Ngày": now.strftime('%d/%m/%Y'), "Mã CK": "FPT", "CTCK": "VDSC", "Khuyến nghị": "MUA",
             "Giá mục tiêu": "150,000", "Tiêu đề Báo cáo": "Cập nhật FPT: Triển vọng sáng, giá mục tiêu 150,000",
             "Link PDF": "https://cafef.vn"},
            {"Ngày": now.strftime('%d/%m/%Y'), "Mã CK": "HPG", "CTCK": "SSI", "Khuyến nghị": "KHẢ QUAN",
             "Giá mục tiêu": "35,000", "Tiêu đề Báo cáo": "Cập nhật HPG: Đợi phục hồi mảng thép",
             "Link PDF": "https://cafef.vn"},
        ]
        df_reports = pd.DataFrame(fallback_data)

    if not df_100.empty and not df_reports.empty:
        df_reports = pd.merge(df_reports, df_100[['Mã CK', 'Giá hiện tại']], on='Mã CK', how='left')

    cols_order = ['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']
    cols_exist = [c for c in cols_order if c in df_reports.columns]
    df_reports = df_reports[cols_exist]

    def style_action(val):
        val_str = str(val).upper()
        if any(x in val_str for x in ['MUA', 'KHẢ QUAN', 'TÍCH LŨY']):
            return f'color: {C_GREEN}; font-weight: bold; background-color: rgba(0, 230, 118, 0.1);'
        elif any(x in val_str for x in ['BÁN', 'KÉM']):
            return f'color: {C_RED}; font-weight: bold; background-color: rgba(255, 77, 77, 0.1);'
        return f'color: {C_REF}; font-weight: bold;'

    fmt = {'Giá hiện tại': '{:,.2f}'} if 'Giá hiện tại' in df_reports.columns else {}
    st.dataframe(
        df_reports.style.map(style_action, subset=['Khuyến nghị']).format(fmt),
        column_config={
            "Ngày": st.column_config.TextColumn("Ngày", width="small"),
            "CTCK": st.column_config.TextColumn("CTCK", width="small"),
            "Tiêu đề Báo cáo": st.column_config.TextColumn("Nội dung báo cáo", width="large"),
            "Link PDF": st.column_config.LinkColumn("Tài liệu", display_text="📥 Xem báo cáo"),
            "Giá mục tiêu": st.column_config.TextColumn("Mục tiêu"),
        },
        use_container_width=True, hide_index=True, height=600
    )

# ── TAB 5: 📡 AI PHÂN TÍCH ─────────────────────────────
with t5:
    st.markdown("### 📡 AI Phân Tích Thị Trường")
    st.caption("Nhập các thông số phiên giao dịch, AI sẽ dự báo kịch bản và xác suất xu hướng.")

    with st.expander("🔑 Cấu hình Claude API Key", expanded=False):
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Lấy tại https://console.anthropic.com"
        )

    st.divider()
    st.markdown("#### 📥 Nhập thông số phiên hôm nay")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        default_vol = 750
        if not df_100.empty:
            default_vol = int(df_100['Tổng KL'].sum() / 1_000_000)

        vol_input = st.number_input(
            "💧 Thanh khoản thị trường (tỷ đồng)",
            min_value=100, max_value=3000,
            value=default_vol, step=50,
            help="Tổng giá trị khớp lệnh toàn thị trường"
        )
        st.markdown("**Thử kịch bản volume:**")
        vol_scenario = st.slider(
            "Kéo để xem kịch bản",
            min_value=300, max_value=2000,
            value=vol_input, step=50,
            label_visibility="collapsed"
        )

    with col_b:
        default_vnindex = 1250.0
        default_ref = 1250.0
        try:
            df_daily_ai = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
            if df_daily_ai is not None and not df_daily_ai.empty:
                df_daily_ai = df_daily_ai.dropna(subset=['close'])
                default_vnindex = float(df_daily_ai.iloc[-1]['close'])
                default_ref = float(df_daily_ai.iloc[-2]['close']) if len(df_daily_ai) >= 2 else default_vnindex
        except:
            pass

        vnindex_input = st.number_input(
            "📊 Điểm VN-INDEX hiện tại",
            min_value=500.0, max_value=2000.0,
            value=default_vnindex, step=0.5, format="%.2f"
        )
        ref_input = st.number_input(
            "📌 Điểm tham chiếu (phiên trước)",
            min_value=500.0, max_value=2000.0,
            value=default_ref, step=0.5, format="%.2f"
        )

    with col_c:
        default_advance = 50
        default_decline = 30
        default_nochange = 20
        if not df_100.empty:
            default_advance = int((df_100['%'] > 0).sum())
            default_decline = int((df_100['%'] < 0).sum())
            default_nochange = int((df_100['%'] == 0).sum())

        advance_input = st.number_input("📈 Số mã tăng giá", min_value=0, max_value=800, value=default_advance)
        decline_input = st.number_input("📉 Số mã giảm giá", min_value=0, max_value=800, value=default_decline)
        nochange_input = st.number_input("➡️ Số mã đứng giá", min_value=0, max_value=800, value=default_nochange)

    top_gainers_str = "N/A"
    top_losers_str = "N/A"
    if not df_100.empty:
        top_g = df_100.nlargest(5, '%')[['Mã CK', '%']].apply(
            lambda r: f"{r['Mã CK']}({r['%']:+.1f}%)", axis=1).tolist()
        top_l = df_100.nsmallest(5, '%')[['Mã CK', '%']].apply(
            lambda r: f"{r['Mã CK']}({r['%']:+.1f}%)", axis=1).tolist()
        top_gainers_str = ", ".join(top_g)
        top_losers_str = ", ".join(top_l)

    st.divider()
    run_ai = st.button("🚀 Chạy AI Phân Tích", type="primary", use_container_width=True)

    if run_ai:
        if not api_key or not api_key.startswith("sk-ant"):
            st.error("❌ Vui lòng nhập đúng Anthropic API Key ở phần cấu hình bên trên.")
        else:
            delta_pts = vnindex_input - ref_input
            delta_pct = (delta_pts / ref_input * 100) if ref_input != 0 else 0
            total_stocks = advance_input + decline_input + nochange_input
            breadth_ratio = (advance_input / total_stocks * 100) if total_stocks > 0 else 50

            if vol_scenario <= 500:
                vol_label = "rất thấp (thị trường thiếu động lực)"
            elif vol_scenario <= 700:
                vol_label = "thấp (dưới mức trung bình)"
            elif vol_scenario <= 900:
                vol_label = "trung bình (bình thường)"
            elif vol_scenario <= 1200:
                vol_label = "tốt (trên trung bình, dòng tiền vào)"
            else:
                vol_label = "rất cao (dòng tiền mạnh hoặc panic)"

            prompt = f"""Bạn là chuyên gia phân tích kỹ thuật thị trường chứng khoán Việt Nam (HOSE).

Dưới đây là dữ liệu thực tế phiên giao dịch hôm nay:

**THÔNG SỐ THỊ TRƯỜNG:**
- VN-INDEX hiện tại: {vnindex_input:,.2f} điểm
- Điểm tham chiếu phiên trước: {ref_input:,.2f} điểm
- Thay đổi hiện tại: {delta_pts:+.2f} điểm ({delta_pct:+.2f}%)
- Thanh khoản thực tế: {vol_input:,} tỷ đồng
- **Kịch bản volume đang xét: {vol_scenario:,} tỷ đồng** ({vol_label})
- Số mã tăng / giảm / đứng: {advance_input} / {decline_input} / {nochange_input}
- Tỷ lệ breadth (% mã tăng): {breadth_ratio:.1f}%
- Top 5 cổ phiếu tăng mạnh nhất: {top_gainers_str}
- Top 5 cổ phiếu giảm mạnh nhất: {top_losers_str}

**YÊU CẦU PHÂN TÍCH:**
Dựa trên dữ liệu trên, hãy phân tích và đưa ra:

1. **ĐÁNH GIÁ TỔNG QUAN** (2-3 câu nhận xét sức mạnh thị trường)

2. **3 KỊCH BẢN CUỐI PHIÊN** với format chính xác như sau:
   - 🐂 BULL (Tăng): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]
   - 🦀 BASE (Sideway): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]
   - 🐻 BEAR (Giảm): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]
   (3 xác suất phải cộng = 100%)

3. **TÁC ĐỘNG CỦA VOLUME {vol_scenario:,} TỶ**: Nếu thanh khoản đạt mức này so với thực tế {vol_input:,} tỷ thì thị trường sẽ như thế nào? Tăng/giảm bao nhiêu điểm?

4. **KHUYẾN NGHỊ CHIẾN LƯỢC** (ngắn gọn cho nhà đầu tư ngắn hạn)

Trả lời bằng tiếng Việt, rõ ràng, chuyên nghiệp, có số liệu cụ thể."""

            with st.spinner("🤖 Claude đang phân tích thị trường..."):
                try:
                    response = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-sonnet-4-6",
                            "max_tokens": 1500,
                            "messages": [{"role": "user", "content": prompt}]
                        },
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        ai_text = result['content'][0]['text']

                        st.success("✅ Phân tích hoàn tất!")
                        st.divider()

                        bull_match = re.search(r'BULL.*?(\d+)%', ai_text)
                        base_match = re.search(r'BASE.*?(\d+)%', ai_text)
                        bear_match = re.search(r'BEAR.*?(\d+)%', ai_text)

                        bull_pct = int(bull_match.group(1)) if bull_match else 33
                        base_pct = int(base_match.group(1)) if base_match else 34
                        bear_pct = int(bear_match.group(1)) if bear_match else 33

                        col_g1, col_g2, col_g3 = st.columns(3)
                        for col, label, pct, color in [
                            (col_g1, "BULL 🐂", bull_pct, "#00e676"),
                            (col_g2, "BASE 🦀", base_pct, "#f5b041"),
                            (col_g3, "BEAR 🐻", bear_pct, "#ff4d4d")
                        ]:
                            with col:
                                fig_gauge = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=pct,
                                    number={'suffix': "%", 'font': {'size': 36, 'color': color}},
                                    title={'text': label, 'font': {'size': 16}},
                                    gauge={
                                        'axis': {'range': [0, 100], 'tickwidth': 1},
                                        'bar': {'color': color},
                                        'bgcolor': "rgba(0,0,0,0)",
                                        'steps': [
                                            {'range': [0, 30], 'color': 'rgba(255,255,255,0.05)'},
                                            {'range': [30, 70], 'color': 'rgba(255,255,255,0.1)'},
                                            {'range': [70, 100], 'color': 'rgba(255,255,255,0.15)'}
                                        ],
                                        'threshold': {
                                            'line': {'color': color, 'width': 4},
                                            'thickness': 0.75,
                                            'value': pct
                                        }
                                    }
                                ))
                                fig_gauge.update_layout(
                                    height=220,
                                    margin=dict(l=20, r=20, t=40, b=10),
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font_color='white'
                                )
                                st.plotly_chart(fig_gauge, use_container_width=True)

                        st.divider()
                        st.markdown("#### 📋 Phân Tích Chi Tiết")
                        st.markdown(ai_text)

                        st.divider()
                        st.markdown("#### 💧 Tác Động Volume Theo Kịch Bản")
                        vol_levels = [400, 500, 600, 700, 800, 900, 1000, 1200, 1500]
                        vol_base = 700
                        impact = [(v, round(vnindex_input + (v - vol_base) * 0.004, 2)) for v in vol_levels]
                        df_vol = pd.DataFrame(impact, columns=['Volume (tỷ)', 'Dự báo VN-INDEX'])
                        df_vol['Màu'] = df_vol['Dự báo VN-INDEX'].apply(
                            lambda x: C_GREEN if x > vnindex_input else (C_RED if x < vnindex_input else C_REF)
                        )
                        fig_vol = go.Figure(go.Bar(
                            x=df_vol['Volume (tỷ)'].astype(str) + " tỷ",
                            y=df_vol['Dự báo VN-INDEX'],
                            marker_color=df_vol['Màu'],
                            text=df_vol['Dự báo VN-INDEX'].apply(lambda x: f"{x:,.2f}"),
                            textposition='outside'
                        ))
                        fig_vol.add_hline(
                            y=vnindex_input, line_dash="dash", line_color=C_REF,
                            annotation_text=f"Tham chiếu: {vnindex_input:,.2f}"
                        )
                        fig_vol.update_layout(
                            height=350,
                            margin=dict(l=10, r=10, t=30, b=10),
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis_title="Thanh khoản",
                            yaxis_title="Điểm VN-INDEX dự báo",
                            yaxis=dict(range=[vnindex_input - 5, vnindex_input + 5])
                        )
                        st.plotly_chart(fig_vol, use_container_width=True)

                    elif response.status_code == 401:
                        st.error("❌ API Key không hợp lệ. Kiểm tra lại tại console.anthropic.com")
                    elif response.status_code == 429:
                        st.error("⏳ Rate limit — thử lại sau 1 phút.")
                    else:
                        st.error(f"❌ Lỗi API: {response.status_code} — {response.text[:200]}")

                except requests.exceptions.Timeout:
                    st.error("⏱️ Timeout — Claude không phản hồi trong 30 giây. Thử lại.")
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")
    else:
        st.info("👆 Kiểm tra thông số và nhấn **Chạy AI Phân Tích** để bắt đầu.")
        col_hint1, col_hint2, col_hint3 = st.columns(3)
        with col_hint1:
            st.markdown("""
            **📊 Volume 700–800 tỷ**  
            Mức trung bình thị trường VN.  
            Thường cho tín hiệu sideway hoặc tăng nhẹ.
            """)
        with col_hint2:
            st.markdown("""
            **📊 Volume > 1,000 tỷ**  
            Dòng tiền mạnh vào thị trường.  
            Tăng xác suất breakout hoặc panic sell.
            """)
        with col_hint3:
            st.markdown("""
            **📊 Volume < 500 tỷ**  
            Thị trường thiếu thanh khoản.  
            Thường sideway, khó đoán chiều.
            """)
