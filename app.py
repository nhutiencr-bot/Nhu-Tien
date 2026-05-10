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

# 2. THIẾT LẬP THỜI GIAN — FIX CUỐI TUẦN: tăng khoảng lùi để đảm bảo đủ phiên giao dịch
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vn_tz)
end_date = now.strftime('%Y-%m-%d')
start_stock = (now - timedelta(days=14)).strftime('%Y-%m-%d')   # Cũ: 7 → Mới: 14
start_index = (now - timedelta(days=10)).strftime('%Y-%m-%d')   # Cũ: 5  → Mới: 10

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

# 4. CÁC HÀM LẤY DỮ LIỆU THỊ TRƯỜNG
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
            # FIX: loại bỏ NaN trước khi dùng
            d = d.dropna(subset=['close', 'volume'])
            if len(d) < 2:
                return None
            curr = d.iloc[-1]['close']
            prev = d.iloc[-2]['close']
            # FIX: tránh chia cho 0
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

# FIX: Cảnh báo rõ ràng nếu không lấy được dữ liệu (thay vì im lặng)
if df_100.empty:
    st.error("⚠️ Không lấy được dữ liệu thị trường. Có thể do vnstock bị giới hạn hoặc ngoài giờ giao dịch. Thử nhấn 🔄 Cập nhật.")

# 6. TABS GIAO DIỆN
t1, t2, t3, t4 = st.tabs(["📈 VN-INDEX & Đóng góp", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Cổ phiếu", "📝 Khuyến Nghị CTCK"])

with t1:
    # --- VN-INDEX metric ---
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
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10),
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
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_b, use_container_width=True)
            else:
                st.info("☕ Biểu đồ tác động chỉ khả dụng trong giờ giao dịch.")
        except:
            st.info("☕ Biểu đồ tác động đang được cập nhật.")

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
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.info("Không có dữ liệu cổ phiếu. Thử nhấn 🔄 Cập nhật.")

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
        # Đảm bảo cột tồn tại trước khi reindex
        cols = ['Ngày', 'Mã CK', 'CTCK', 'Khuyến nghị', 'Giá hiện tại', 'Giá mục tiêu', 'Tiêu đề Báo cáo', 'Link PDF']
        cols_exist = [c for c in cols if c in df_reports.columns]
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
            "Tiêu đề Báo cáo": st.column_config.TextColumn("Nội dung báo cáo
