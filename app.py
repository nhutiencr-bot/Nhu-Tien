import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import concurrent.futures # Thư viện xử lý đa luồng giúp tăng tốc x20 lần

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=2)).strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')

# 3. HÀM QUÉT TOÀN THỊ TRƯỜNG VÀ TÌM TOP 100 (SIÊU TỐC)
@st.cache_data(ttl=86400) # Chỉ tải danh sách công ty 1 lần/ngày
def get_company_sectors():
    try:
        df = listing_companies()
        # Lọc lấy sàn HOSE và bỏ các mã chứng quyền (độ dài tên mã > 3)
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        # Tạo từ điển map Mã CK -> Tên Ngành
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except:
        return {}

@st.cache_data(ttl=300) # Làm mới dữ liệu Top 100 mỗi 5 phút
def get_dynamic_top_100():
    sector_dict = get_company_sectors()
    tickers = list(sector_dict.keys())
    
    # Hàm con tải dữ liệu 1 mã
    def fetch_ticker(ticker):
        try:
            df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
            if len(df) >= 2:
                close_today = df.iloc[-1]['close']
                close_yest = df.iloc[-2]['close']
                change = close_today - close_yest
                pct_change = (change / close_yest) * 100
                volume = df.iloc[-1]['volume']
                return {
                    'Mã CK': ticker,
                    'Nhóm Ngành': sector_dict.get(ticker, 'Khác'),
                    'Giá': close_today,
                    '+/-': round(change, 2),
                    '%': round(pct_change, 2),
                    'Tổng KL': int(volume)
                }
        except:
            return None

    results = []
    # Chạy đa luồng (20 luồng) để quét ~400 mã trong chớp mắt
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0:
                results.append(res)
                
    df_market = pd.DataFrame(results)
    
    # LỌC TOP 100 MÃ CÓ THANH KHOẢN LỚN NHẤT NGÀY HÔM NAY
    if not df_market.empty:
        df_market = df_market.sort_values(by='Tổng KL', ascending=False).head(100)
        
    return df_market

# 4. TẠO GIAO DIỆN 3 TABS
tab1, tab2, tab3 = st.tabs(["📈 VN-INDEX", "🗺️ Bản đồ dòng tiền (Động)", "📊 Top 100 Active (Realtime)"])

# ==========================================
# TAB 1: VN-INDEX REALTIME
# ==========================================
with tab1:
    @st.cache_data(ttl=60)
    def get_realtime_index():
        return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

    try:
        df_index = get_realtime_index()
        if not df_index.empty:
            latest_data = df_index.iloc[-1]
            prev_data = df_index.iloc[-2]
            current_score = latest_data['close']
            point_change = current_score - prev_data['close']
            
            st.metric(label=f"VN-INDEX (Lúc {latest_data['time']})", value=f"{current_score:,.2f}", delta=f"{point_change:,.2f} điểm")
            st.line_chart(df_index[['time', 'close']].set_index('time'))
    except Exception as e:
        st.error("Chưa có dữ liệu VN-INDEX hiện tại.")

# TẢI DỮ LIỆU TOP 100 CHUNG CHO TAB 2 & 3
df_top100 = get_dynamic_top_100()

# ==========================================
# TAB 2: BẢN ĐỒ NHIỆT (HEATMAP DÒNG TIỀN)
# ==========================================
with tab2:
    if not df_top100.empty:
        # Treemap giờ đây sẽ tự động sắp xếp theo Top 100 mã thực tế của ngày
        fig = px.treemap(
            df_top100, 
            path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], 
            values='Tổng KL', 
            color='%', 
            color_continuous_scale=['#ff4d4d', '#2b2b2b', '#00e676'], 
            color_continuous_midpoint=0,
            custom_data=['%', 'Tổng KL', 'Giá']
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%<br>KL: %{customdata[1]:,.0f}",
            textposition="middle center",
            textfont=dict(color="white", size=13)
        )
        fig.update_layout(margin=dict(t=20, l=10, r=10, b=10), height=650)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⏳ Đang tải dữ liệu Bản đồ nhiệt...")

# ==========================================
# TAB 3: BẢNG ĐIỆN TOP 100 (TỰ ĐỘNG CẬP NHẬT)
# ==========================================
with tab3:
    if not df_top100.empty:
        st.markdown("### 📊 Biến động 100 cổ phiếu có thanh khoản lớn nhất hôm nay")
        
        # Hàm tô màu
        def color_change(val):
            if pd.isna(val): return ''
            if val > 0: return 'color: #00e676; font-weight: bold;'
            elif val < 0: return 'color: #ff4d4d; font-weight: bold;'
            else: return 'color: #f5b041; font-weight: bold;'
            
        format_dict = {
            'Giá': '{:,.2f}',
            '+/-': '{:+,.2f}',
            '%': '{:+,.2f}%',
            'Tổng KL': '{:,.0f}'
        }
        
        try:
            styled_df = df_top100.style.format(format_dict).map(color_change, subset=['+/-', '%'])
        except:
            styled_df = df_top100.style.format(format_dict).applymap(color_change, subset=['+/-', '%'])
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
    else:
        st.info("⏳ Đang tải dữ liệu Bảng điện...")

# Tự động làm mới trang sau 60 giây
time.sleep(60)
st.rerun()
