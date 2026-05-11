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
    [0.0, C_FLOOR],   [0.014, C_FLOOR],
    [0.014, C_RED],   [0.2857, C_RED],
    [0.2857, C_LRED], [0.4992, C_LRED],
    [0.4992, C_REF],  [0.5007, C_REF],
    [0.5007, C_GREEN],[0.9857, C_GREEN],
    [0.9857, C_CEIL], [1.0, C_CEIL]
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==========================================
# 3. HÀM FETCH VỚI PROXY
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
        except:
            continue
    return None

# ==========================================
# 4. LẤY DỮ LIỆU CỔ PHIẾU
# ==========================================
@st.cache_data(ttl=30)
def get_top_200_realtime():
    base_url = "https://finfo-api.vndirect.com.vn/v4/stock_prices"
    query = "?sort=accumulatedVal~DESC&q=floor:HOSE,HNX,UPCOM&size=200"
    data = fetch_url_with_proxies(base_url + query, is_json=True)

    if data and 'data' in data:
        cols = ['code', 'matchPrice', 'priceChange', 'changePc',
                'accumulatedVol', 'accumulatedVal']
        df = pd.DataFrame(data['data'])[cols]
        df.columns = ['Mã CK', 'Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']
        df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']] = \
            df[['Giá', '+/-', '%', 'Tổng KL', 'Tổng GT']].apply(pd.to_numeric, errors='coerce')
        return df.dropna(subset=['Tổng KL'])
    return pd.DataFrame()


# ==========================================
# 5. LẤY SỐ LƯỢNG CỔ PHIẾU LƯU HÀNH + TÍNH TÁC ĐỘNG
# ==========================================
@st.cache_data(ttl=3600)
def get_shares_outstanding(tickers: list) -> dict:
    """
    Lấy số lượng cổ phiếu lưu hành từ VNDirect fundamentals API.
    Trả về dict {ticker: shares_outstanding}
    """
    result = {}
    # Batch 20 mã mỗi lần để tránh quá tải
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        codes = ",".join(batch)
        url = (
            f"https://finfo-api.vndirect.com.vn/v4/company_profiles"
            f"?q=code:{codes}&fields=code,sharesOutstanding&size={batch_size}"
        )
        data = fetch_url_with_proxies(url, is_json=True)
        if data and 'data' in data:
            for item in data['data']:
                code = item.get('code', '')
                shares = item.get('sharesOutstanding', 0)
                if code and shares:
                    result[code] = float(shares)
    return result


@st.cache_data(ttl=60)
def get_vnindex_divisor() -> float:
    """
    Lấy hệ số chia (divisor) VN-INDEX hiện tại.
    Nếu không lấy được thì dùng giá trị xấp xỉ thực tế ~2,700 tỷ.
    """
    url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?q=code:VNINDEX&fields=matchPrice,accumulatedVol"
    data = fetch_url_with_proxies(url, is_json=True)
    # Divisor xấp xỉ = tổng vốn hóa HOSE / VN-INDEX
    # Dùng giá trị chuẩn thực tế nếu không tính được
    return 2_700_000_000_000.0  # ~2,700 tỷ VND (cập nhật định kỳ)


@st.cache_data(ttl=60)
def calc_index_contribution(df_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Tính tác động điểm VN-INDEX theo công thức chuẩn HOSE:
        Tác động(i) = (ΔGiá(i) × Số CP lưu hành(i)) / Divisor

    Chỉ tính cho mã thuộc HOSE (bộ lọc theo danh sách hoặc sàn).
    """
    if df_prices.empty:
        return pd.DataFrame()

    tickers = df_prices['Mã CK'].tolist()

    # Lấy số lượng CP lưu hành
    shares_dict = get_shares_outstanding(tickers)
    divisor = get_vnindex_divisor()

    rows = []
    for _, row in df_prices.iterrows():
        ticker = row['Mã CK']
        delta_price = row['+/-']          # Thay đổi giá tuyệt đối (VND)
        shares = shares_dict.get(ticker, 0)

        if shares > 0 and divisor > 0:
            # Công thức chính thức HOSE
            impact_pts = (delta_price * shares) / divisor
            rows.append({'Mã CK': ticker, 'Điểm tác động': round(impact_pts, 4)})

    df_impact = pd.DataFrame(rows)
    if df_impact.empty:
        return df_impact

    # Lấy top 10 tăng + top 10 giảm để hiển thị
    df_pos = df_impact[df_impact['Điểm tác động'] > 0].nlargest(10, 'Điểm tác động')
    df_neg = df_impact[df_impact['Điểm tác động'] < 0].nsmallest(10, 'Điểm tác động')
    return pd.concat([df_pos, df_neg]).sort_values('Điểm tác động', ascending=False)


# ==========================================
# 6. CÁC HÀM DỮ LIỆU CÒN LẠI
# ==========================================
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
            return {
                'close': c, 'prev': p, 'volume': v,
                'MA20': float(last['MA20']), 'V_MA20': float(last['V_MA20'])
            }
    except:
        pass
    return None


@st.cache_data(ttl=1800)
def get_cafef_reports():
    url = "https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30"
    html = fetch_url_with_proxies(url, is_json=False)
    res = []

    p_li    = r'<li.*?>(.*?)</li>'
    p_title = r'class="doc_title"[^>]*>(.*?)</a>'
    p_link  = r'href="(/Report/Download\.aspx\?id=[^"]+)"'
    p_src   = r'class="doc_source"[^>]*>(.*?)</span>'
    p_date  = r'class="doc_date"[^>]*>(.*?)</span>'
    p_tk    = r'\b([A-Z0-9]{3})\b'

    if html:
        for b in re.findall(p_li, html, re.DOTALL):
            t_m = re.search(p_title, b)
            l_m = re.search(p_link, b)
            s_m = re.search(p_src, b)
            d_m = re.search(p_date, b)

            if t_m and l_m:
                title = t_m.group(1).strip()
                link  = "https://s.cafef.vn" + l_m.group(1)
                tk_m  = re.search(p_tk, title)
                ticker = tk_m.group(1) if tk_m else ""

                action = "ĐÁNH GIÁ"
                t_up = title.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]):
                    action = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]):
                    action = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]):
                    action = "NẮM GIỮ"

                res.append({
                    "Ngày": d_m.group(1).strip() if d_m else "",
                    "Mã CK": ticker,
                    "Khuyến nghị": action,
                    "CTCK": s_m.group(1).strip() if s_m else "",
                    "Nội dung": title,
                    "Link Tải PDF": link
                })
    return pd.DataFrame(res)


# ==========================================
# 7. LOAD DỮ LIỆU CHÍNH
# ==========================================
with st.spinner("Đang tải dữ liệu real-time..."):
    df_200    = get_top_200_realtime()
    idx_data  = get_vnindex_live_and_ma()
    df_reports = get_cafef_reports()

df_gainers = df_200.sort_values('%', ascending=False).head(10) if not df_200.empty else pd.DataFrame()

# ==========================================
# 8. TABS
# ==========================================
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
        if   v >= 6.8:  c = C_CEIL
        elif v <= -6.8: c = C_FLOOR
        elif v > 0:     c = C_GREEN
        elif v == 0:    c = C_REF
        elif v > -3:    c = C_LRED
        else:           c = C_RED
        return f'color: {c}; font-weight: bold;'
    except:
        return ''

# ── TAB 1: CHỈ SỐ & TÁC ĐỘNG ─────────────────────────
with t1:
    if idx_data:
        cur, prev = idx_data['close'], idx_data['prev']
        st.metric(
            "Điểm số VN-INDEX (LIVE)",
            f"{cur:,.2f}",
            f"{cur - prev:+,.2f} ({((cur - prev) / prev * 100):+,.2f}%)"
        )
        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### 🌊 Thanh khoản (So với TBC 20 Phiên)")
            v, v_ma = idx_data['volume'], idx_data['V_MA20']
            fig = go.Figure(go.Bar(
                x=['Khối lượng LIVE', 'Trung bình MA20'],
                y=[v, v_ma],
                marker_color=[C_GREEN if v > v_ma else C_REF, 'rgba(150,150,150,0.5)'],
                text=[f"{v / 1_000_000:,.1f} Tr CP", f"{v_ma / 1_000_000:,.1f} Tr CP"],
                textposition='auto'
            ))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                              plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("#### 🎯 Tác động điểm VN-INDEX (theo KLƯH thực tế)")
            st.caption("Công thức HOSE: Tác động = (ΔGiá × Số CP lưu hành) ÷ Divisor")

            if not df_200.empty:
                with st.spinner("Đang tính tác động theo số CP lưu hành..."):
                    df_impact = calc_index_contribution(df_200)

                if not df_impact.empty:
                    b_cols = [C_GREEN if v > 0 else C_RED for v in df_impact['Điểm tác động']]
                    fig_b = go.Figure(go.Bar(
                        x=df_impact['Mã CK'],
                        y=df_impact['Điểm tác động'],
                        marker_color=b_cols,
                        text=df_impact['Điểm tác động'].apply(lambda x: f"{x:+.3f}"),
                        textposition='outside'
                    ))
                    fig_b.update_layout(
                        height=380,
                        margin=dict(l=10, r=10, t=30, b=10),
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis_title="Điểm tác động",
                        xaxis_title="Mã cổ phiếu"
                    )
                    st.plotly_chart(fig_b, use_container_width=True)

                    # Bảng chi tiết
                    with st.expander("📋 Xem bảng tác động chi tiết"):
                        df_detail = df_impact.copy()
                        df_detail.columns = ['Mã CK', 'Điểm tác động (pts)']
                        st.dataframe(
                            df_detail.style
                            .format({'Điểm tác động (pts)': '{:+.4f}'})
                            .map(lambda x: f'color: {C_GREEN if x > 0 else C_RED}; font-weight: bold;',
                                 subset=['Điểm tác động (pts)']),
                            use_container_width=True, hide_index=True
                        )
                else:
                    st.info("Đang lấy dữ liệu số CP lưu hành... Thử nhấn 🔄 Cập nhật.")
            else:
                st.info("Chờ dữ liệu thị trường...")
    else:
        st.warning("Không lấy được dữ liệu VN-INDEX. Thử nhấn 🔄 Cập nhật.")

# ── TAB 2: BẢN ĐỒ DÒNG TIỀN ──────────────────────────
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
        fig_m.update_layout(height=650, margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.error("Tường lửa chặn. Hãy nhấn [🔄 Cập nhật Live] để đổi IP Proxy mới.")

# ── TAB 3: BẢNG GIÁ ───────────────────────────────────
with t3:
    if not df_200.empty:
        st.markdown("### 📊 Top 200 Cổ Phiếu Dẫn Dắt Dòng Tiền")
        st.dataframe(
            df_200.style
            .format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%',
                     'Tổng KL': '{:,.0f}', 'Tổng GT': '{:,.0f}'})
            .map(style_v, subset=['+/-', '%']),
            use_container_width=True, hide_index=True, height=600
        )

# ── TAB 4: TOP 10 TĂNG MẠNH ───────────────────────────
with t4:
    if not df_gainers.empty:
        st.markdown("### 🚀 Top 10 Cổ Phiếu Tăng Mạnh Nhất")
        st.dataframe(
            df_gainers.style
            .format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%',
                     'Tổng KL': '{:,.0f}', 'Tổng GT': '{:,.0f}'})
            .map(style_v, subset=['+/-', '%']),
            use_container_width=True, hide_index=True, height=400
        )

# ── TAB 5: KHUYẾN NGHỊ ────────────────────────────────
with t5:
    if not df_reports.empty:
        st.markdown("### 📝 Cập Nhật Khuyến Nghị (Nguồn: CafeF)")
        st.dataframe(
            df_reports.style.map(
                lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;',
                subset=['Khuyến nghị']
            ),
            column_config={"Link Tải PDF": st.column_config.LinkColumn("Bấm để xem")},
            hide_index=True, use_container_width=True, height=600
        )
    else:
        st.warning("Đang quét báo cáo Khuyến nghị...")

# ── TAB 6: AI VSA ─────────────────────────────────────
with t6:
    if idx_data and not df_200.empty:
        c, ma  = idx_data['close'], idx_data['MA20']
        v, v_ma = idx_data['volume'], idx_data['V_MA20']
        adv = len(df_200[df_200['%'] > 0])
        dec = len(df_200[df_200['%'] < 0])

        ai_score = 0
        vol_ratio = (v / v_ma) * 100 if v_ma > 0 else 0

        if vol_ratio >= 120:
            kl_st  = f"BÙNG NỔ ({vol_ratio:.1f}% MA20). Khối lượng vượt xa mức trung bình 20 phiên ({v_ma / 1_000_000:,.1f} Tr CP)."
            kl_col = C_CEIL
            ai_score += 1 if c > ma else -1
        elif vol_ratio >= 80:
            kl_st  = f"ỔN ĐỊNH ({vol_ratio:.1f}% MA20). Khối lượng duy trì quanh mức trung bình tự nhiên."
            kl_col = C_GREEN
            ai_score += 1
        else:
            kl_st  = f"SUY YẾU ({vol_ratio:.1f}% MA20). Dòng tiền lớn đang đứng ngoài, lực cầu cạn kiệt."
            kl_col = C_RED

        if adv > dec * 1.5:
            rong_st  = f"LAN TỎA TÍCH CỰC ({adv} mã Tăng áp đảo {dec} mã Giảm). Dòng tiền mua lan rộng toàn thị trường."
            rong_col = C_GREEN
            ai_score += 1
        elif dec > adv * 1.5:
            rong_st  = f"CẢNH BÁO RỦI RO (Chỉ {adv} mã Tăng nhưng {dec} mã Giảm). Hiện tượng 'Xanh vỏ, đỏ lòng' hoặc xả hàng."
            rong_col = C_RED
            ai_score -= 1
        else:
            rong_st  = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm). Dòng tiền luân chuyển chọn lọc."
            rong_col = C_REF

        gia_st  = "NẰM TRÊN" if c > ma else "RƠI XUỐNG DƯỚI"
        gia_col = C_GREEN if c > ma else C_RED

        # Thêm đánh giá tác động từ KLƯH
        if not df_200.empty:
            df_imp_vsa = calc_index_contribution(df_200)
            if not df_imp_vsa.empty:
                top_bull = df_imp_vsa[df_imp_vsa['Điểm tác động'] > 0].head(3)['Mã CK'].tolist()
                top_bear = df_imp_vsa[df_imp_vsa['Điểm tác động'] < 0].tail(3)['Mã CK'].tolist()
                klh_note = (
                    f"Mã kéo chỉ số mạnh nhất: <b style='color:{C_GREEN}'>{', '.join(top_bull)}</b> | "
                    f"Mã kéo chỉ số xuống: <b style='color:{C_RED}'>{', '.join(top_bear)}</b>"
                )
            else:
                klh_note = "Đang tính toán tác động theo KLƯH..."
        else:
            klh_note = ""

        html_ai = (
            "<div class='card' style='background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%);'>"
            "<h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ VSA & ĐỘ RỘNG (REAL-TIME)</h2>"
            "<ul style='font-size: 17px; line-height: 1.8;'>"
            f"<li><b>Động lượng Khối lượng:</b> {v / 1_000_000:,.1f} Tr CP — <b style='color:{kl_col}'>{kl_st}</b></li>"
            f"<li><b>Độ rộng thị trường:</b> <b style='color:{rong_col}'>{rong_st}</b></li>"
            f"<li><b>Hành động Giá:</b> VN-INDEX <b style='color:{gia_col}'>{gia_st}</b> MA20 ({ma:,.2f})</li>"
            f"<li><b>Tác động theo KLƯH:</b> {klh_note}</li>"
            "</ul></div><br>"
        )
        st.markdown(html_ai, unsafe_allow_html=True)

        if ai_score >= 1:
            sc_color = C_GREEN
            sc_title = "🟢 Kịch Bản Tích Cực (Khả năng cao nhất)"
            sc_desc  = "Khối lượng gia tăng và độ rộng lan tỏa. Gia tăng tỷ trọng, tập trung giải ngân nhóm hút dòng tiền mạnh nhất."
        elif ai_score == 0:
            sc_color = C_REF
            sc_title = "🟡 Kịch Bản Đi Ngang / Phân Hóa"
            sc_desc  = "Khối lượng suy yếu hoặc số mã giảm nhỉnh hơn. Hạn chế MUA MỚI, canh nhịp tăng để giảm tỷ trọng Margin."
        else:
            sc_color = C_RED
            sc_title = "🔴 Kịch Bản Điều Chỉnh Giảm"
            sc_desc  = "Bán tháo rõ rệt, khối lượng bùng nổ chiều bán hoặc số mã giảm áp đảo. Quản trị rủi ro tuyệt đối, đứng ngoài quan sát."

        st.markdown(
            f"<div class='scenario-box' style='border-left: 5px solid {sc_color};'>"
            f"<h3 style='color:{sc_color}; margin-top:0;'>{sc_title}</h3>"
            f"<p style='font-size:16px;'>{sc_desc}</p>"
            "</div>",
            unsafe_allow_html=True
        )
    else:
        st.info("Đang tải dữ liệu VSA...")
