import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

# ── Import vnstock (hỗ trợ cả version cũ và mới) ─────
try:
    from vnstock import Vnstock
    VNSTOCK_V = "new"
except ImportError:
    try:
        from vnstock import stock_historical_data, listing_companies
        VNSTOCK_V = "old"
    except ImportError:
        VNSTOCK_V = None

# ══════════════════════════════════════════════════════
# 1. CÀI ĐẶT GIAO DIỆN
# ══════════════════════════════════════════════════════
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
        font-size: 18px; font-weight: 600;
    }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 2. THỜI GIAN — luôn lùi về phiên giao dịch gần nhất
# ══════════════════════════════════════════════════════
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now   = datetime.now(vn_tz)

def last_trading_day(dt):
    d = dt
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

last_td     = last_trading_day(now if now.hour >= 15 else now - timedelta(days=1))
end_date    = last_td.strftime('%Y-%m-%d')
start_stock = (last_td - timedelta(days=20)).strftime('%Y-%m-%d')
start_index = (last_td - timedelta(days=14)).strftime('%Y-%m-%d')

is_trading = (now.weekday() < 5) and (
    (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 30)
)

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🧚‍♀️ FAIRY INVEST - Dashboard")
with col_status:
    if is_trading:
        st.success(f"🟢 ĐANG GIAO DỊCH | {now.strftime('%H:%M')}")
    else:
        st.warning(f"🔴 ĐÃ ĐÓNG CỬA | Phiên {end_date}")
    if st.button("🔄 Cập nhật dữ liệu mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ══════════════════════════════════════════════════════
# 3. MÀU SẮC
# ══════════════════════════════════════════════════════
C_CEIL  = '#cc00ff'
C_GREEN = '#00e676'
C_REF   = '#f5b041'
C_RED   = '#ff4d4d'
C_DRED  = '#b30000'
C_FLOOR = '#00e5ff'

MAP_COLORS = [
    [0.0,   C_FLOOR], [0.014, C_FLOOR],
    [0.014, C_DRED],  [0.285, C_DRED],
    [0.285, C_RED],   [0.499, C_RED],
    [0.499, C_REF],   [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN],
    [0.985, C_CEIL],  [1.0,   C_CEIL],
]

# ══════════════════════════════════════════════════════
# 4. HÀM LẤY DỮ LIỆU
# ══════════════════════════════════════════════════════

def _fetch_history(symbol, start, end, interval='1D', source='VCI'):
    try:
        if VNSTOCK_V == "new":
            obj = Vnstock().stock(symbol=symbol, source=source)
            df  = obj.quote.history(start=start, end=end, interval=interval)
        elif VNSTOCK_V == "old":
            asset_type = 'index' if symbol in ('VNINDEX', 'VN30', 'HNX') else 'stock'
            df = stock_historical_data(symbol, start, end, interval, asset_type)
        else:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df.columns = [c.lower() for c in df.columns]
        for alt in ['date', 'tradingdate', 'datetime']:
            if alt in df.columns and 'time' not in df.columns:
                df['time'] = df[alt]
        return df.dropna(subset=['close'])
    except Exception as e:
        print(f"_fetch_history({symbol}): {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_hose_tickers():
    try:
        if VNSTOCK_V == "new":
            obj = Vnstock().stock(symbol='ACB', source='VCI')
            df  = obj.listing.symbols_by_exchange()
            df.columns = [c.lower() for c in df.columns]
            for xcol in ['exchange', 'comgroupcode', 'floor']:
                if xcol in df.columns:
                    sub = df[df[xcol].str.upper() == 'HOSE']
                    for tcol in ['ticker', 'symbol', 'code']:
                        if tcol in sub.columns:
                            return sub[tcol].tolist()
        elif VNSTOCK_V == "old":
            df = listing_companies()
            return df[df['comGroupCode'] == 'HOSE']['ticker'].tolist()
    except Exception as e:
        print(f"get_hose_tickers: {e}")
    return []


@st.cache_data(ttl=120)
def get_market_data():
    tickers = get_hose_tickers()
    if not tickers:
        return pd.DataFrame()

    def fetch(t):
        try:
            d = _fetch_history(t, start_stock, end_date)
            if d.empty or len(d) < 2:
                return None
            curr = float(d.iloc[-1]['close'])
            prev = float(d.iloc[-2]['close'])
            if prev == 0:
                return None
            vol = int(d.iloc[-1]['volume']) if 'volume' in d.columns else 0
            return {
                'Mã CK':        t,
                'Giá hiện tại': curr,
                '+/-':          round(curr - prev, 2),
                '%':            round((curr - prev) / prev * 100, 2),
                'Tổng KL':      vol,
            }
        except:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        res = list(exe.map(fetch, tickers))

    df = pd.DataFrame([r for r in res if r])
    return df.sort_values('Tổng KL', ascending=False).head(100) if not df.empty else df


@st.cache_data(ttl=300)
def get_vnindex_daily():
    return _fetch_history('VNINDEX', start_index, end_date, '1D')


@st.cache_data(ttl=300)
def get_vnindex_intraday():
    return _fetch_history('VNINDEX', start_index, end_date, '1')


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
def get_cafef_reports():
    reports = []
    try:
        url = "https://cafef.vn/du-lieu/phan-tich-bao-cao.chn"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        soup  = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', {'id': 'tblGridData'})
        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                date_pub  = cols[0].text.strip()
                ticker    = cols[1].text.strip()
                source    = cols[2].text.strip()
                title_tag = cols[3].find('a')
                title     = title_tag.text.strip() if title_tag else cols[3].text.strip()
                link_pdf  = "N/A"
                if title_tag and title_tag.has_attr('href'):
                    href     = title_tag['href']
                    link_pdf = ("https://cafef.vn" + href) if href.startswith('/') else href
                am = re.search(
                    r'(MUA|BÁN|NẮM GIỮ|KHẢ QUAN|KÉM KHẢ QUAN|TÍCH LŨY|TRUNG LẬP)',
                    title, re.IGNORECASE)
                action = am.group(1).upper() if am else "ĐÁNH GIÁ"
                pm = re.search(r'mục tiêu.*?([\d,\.]+)', title, re.IGNORECASE)
                target_price = pm.group(1) if pm else "N/A"
                if ticker:
                    reports.append({
                        "Ngày": date_pub, "Mã CK": ticker, "CTCK": source,
                        "Khuyến nghị": action, "Giá mục tiêu": target_price,
                        "Tiêu đề Báo cáo": title, "Link PDF": link_pdf,
                    })
    except Exception as e:
        print(f"CafeF error: {e}")
    return pd.DataFrame(reports)


# ══════════════════════════════════════════════════════
# 5. LOAD DỮ LIỆU CHÍNH
# ══════════════════════════════════════════════════════
with st.spinner("Đang tải dữ liệu thị trường..."):
    df_100     = get_market_data()
    df_vni_day = get_vnindex_daily()

if df_100.empty:
    st.error("⚠️ Không lấy được dữ liệu cổ phiếu. Thử nhấn 🔄 Cập nhật.")

# Tự động tính các chỉ số từ phiên gần nhất
auto_vnindex = 1250.0
auto_ref     = 1250.0
auto_vol_mkt = 750

if not df_vni_day.empty and len(df_vni_day) >= 2:
    auto_vnindex = float(df_vni_day.iloc[-1]['close'])
    auto_ref     = float(df_vni_day.iloc[-2]['close'])
if not df_100.empty:
    auto_vol_mkt = max(1, int(df_100['Tổng KL'].sum() / 1_000_000))

# ══════════════════════════════════════════════════════
# 6. TABS
# ══════════════════════════════════════════════════════
t1, t2, t3, t4, t5 = st.tabs([
    "📈 VN-INDEX & Đóng góp",
    "🗺️ Bản đồ Dòng tiền",
    "📊 Top 100 Cổ phiếu",
    "📝 Khuyến Nghị CTCK",
    "📡 AI Phân Tích",
])

# ── TAB 1 ─────────────────────────────────────────────
with t1:
    if not df_vni_day.empty and len(df_vni_day) >= 2:
        cur      = float(df_vni_day.iloc[-1]['close'])
        ref_prev = float(df_vni_day.iloc[-2]['close'])
        time_str = str(df_vni_day.iloc[-1]['time'])[:10]
        delta_val = cur - ref_prev
        delta_pct = (delta_val / ref_prev * 100) if ref_prev != 0 else 0
        st.metric(
            f"📊 VN-INDEX — Phiên {time_str}",
            f"{cur:,.2f}",
            f"{delta_val:+,.2f} ({delta_pct:+,.2f}%)",
        )
    else:
        st.info("📊 Chưa có dữ liệu VN-INDEX.")
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🌊 Thanh khoản tích luỹ")
        try:
            df_idx = get_vnindex_intraday()
            if df_idx is not None and not df_idx.empty and 'time' in df_idx.columns:
                df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
                dates = sorted(df_idx['date'].unique())
                df_t  = df_idx[df_idx['date'] == dates[-1]].copy()
                df_t['ts'] = pd.to_datetime(df_t['time']).dt.strftime('%H:%M')
                fig = go.Figure()
                if len(dates) >= 2:
                    df_y = df_idx[df_idx['date'] == dates[-2]].copy()
                    df_y['ts'] = pd.to_datetime(df_y['time']).dt.strftime('%H:%M')
                    fig.add_trace(go.Scatter(
                        x=df_y['ts'], y=df_y['volume'].cumsum(),
                        fill='tozeroy', name='Phiên trước',
                        line=dict(color='rgba(150,150,150,0.5)'),
                    ))
                fig.add_trace(go.Scatter(
                    x=df_t['ts'], y=df_t['volume'].cumsum(),
                    fill='tozeroy', name='Phiên gần nhất',
                    line=dict(color=C_GREEN),
                ))
                fig.update_layout(
                    height=380, margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", y=1.1),
                    plot_bgcolor='rgba(0,0,0,0)',
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("☕ Dữ liệu intraday không khả dụng ngoài giờ giao dịch.")
        except:
            st.info("☕ Đồ thị thanh khoản tạm thời không khả dụng.")

    with c2:
        st.markdown("#### 🎯 Tác động tới VN-INDEX")
        try:
            df_c = get_index_contrib()
            if not df_c.empty:
                df_res = pd.concat([
                    df_c[df_c['Điểm'] > 0].nlargest(10, 'Điểm'),
                    df_c[df_c['Điểm'] < 0].nsmallest(10, 'Điểm'),
                ]).sort_values('Điểm', ascending=False)
                b_cols = [C_GREEN if v > 0 else C_RED for v in df_res['Điểm']]
                fig_b  = go.Figure(go.Bar(
                    x=df_res['Mã CK'], y=df_res['Điểm'],
                    marker_color=b_cols,
                    text=df_res['Điểm'].apply(lambda x: f"{x:+.2f}"),
                    textposition='outside',
                ))
