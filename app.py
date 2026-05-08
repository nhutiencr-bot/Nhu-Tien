import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=2)).strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')

# 3. DANH SÁCH 110 CỔ PHIẾU THANH KHOẢN CAO NHẤT THEO NGÀNH
SECTORS = {
    'Ngân hàng': ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'STB', 'ACB', 'SHB', 'HDB', 'VIB', 'SSB', 'EIB', 'MSB', 'OCB', 'LPB', 'TPB', 'NAB'],
    'Bất động sản': ['VHM', 'VIC', 'VRE', 'NVL', 'DIG', 'PDR', 'KDH', 'DXG', 'CEO', 'NLG', 'HDC', 'SCR', 'KHG', 'CRE', 'TCH', 'IJC', 'NTL'],
    'Chứng khoán': ['SSI', 'VND', 'VCI', 'HCM', 'VIX', 'SHS', 'MBS', 'FTS', 'BSI', 'CTS', 'AGR', 'VDS', 'ORS'],
    'Thép / Vật liệu': ['HPG', 'HSG', 'NKG', 'HT1', 'BCC', 'KSB', 'VGC'],
    'Xây dựng / ĐTC': ['VCG', 'HHV', 'LCG', 'FCN', 'C4G', 'CTD', 'HBC', 'HUT'],
    'Bán lẻ / Tiêu dùng': ['MWG', 'VNM', 'MSN', 'PNJ', 'DGW', 'FRT', 'SAB', 'KDC', 'PET', 'HAX'],
    'Năng lượng / Dầu khí': ['GAS', 'PVD', 'PVS', 'BSR', 'PLX', 'POW', 'NT2', 'GEG', 'PC1'],
    'Hóa chất / Phân bón': ['DGC', 'DCM', 'DPM', 'CSV', 'LAS'],
    'Cảng biển / Logistics': ['GMD', 'HAH', 'VSC', 'PVT'],
    'Khu công nghiệp': ['KBC', 'IDC', 'SZC', 'PHR', 'GVR', 'SIP'],
    'Công nghệ / Viễn thông': ['FPT', 'CMG', 'VGI', 'FOX'],
    'Nông nghiệp / Thủy sản': ['HAG', 'DBC', 'BAF', 'VHC', 'ANV', 'ASM', 'IDI']
}

# 4. HÀM LẤY DỮ LIỆU THỊ TRƯỜNG (Có Cache để web chạy nhanh)
@st.cache_data(ttl=300) # Cập nhật 5 phút / lần
def get_market_data():
    data = []
    for sector, tickers in SECTORS.items():
        for ticker in tickers:
            try:
                df = stock_historical_data(symbol=ticker, start_date=start_date_stock, end_date=end_date, resolution='1D', type='stock')
                if len(df) >= 2:
                    close_today = df.iloc[-1]['close']
                    close_yest = df.iloc[-2]['close']
                    change = close_today - close_yest
                    pct_change = (change / close_yest) * 100
                    volume = df.iloc[-1]['volume']
                    
                    data.append({
                        'Mã CK': ticker,
                        'Nhóm Ngành': sector,
                        'Giá': close_today,
                        '+/-': round(change, 2),
                        '%': round(pct_change, 2),
                        'Tổng KL': int(volume)
                    })
            except:
                continue
    return pd.DataFrame(data)

# 5. TẠO GIAO DIỆN 3 TABS
tab1, tab2, tab3 = st.tabs(["📈 VN-INDEX", "🗺️ Bản đồ dòng tiền (Heatmap)", "📊 Top 100 KLGD"])

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

# LẤY DỮ LIỆU CHUNG CHO TAB 2 VÀ TAB 3
df_market = get_market_data()

# ==========================================
# TAB 2: BẢN ĐỒ NHIỆT (HEATMAP DÒNG TIỀN)
# ==========================================
with tab2:
    if not df_market.empty:
        # Vẽ biểu đồ Treemap
        fig = px.treemap(
            df_market, 
            path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], 
            values='Tổng KL', 
            color='%', 
            color_continuous_scale=['#ff4d4d', '#2b2b2b', '#00e676'], # Đỏ - Đen - Xanh
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
        st.info("⏳ Đang tải dữ liệu Bản đồ nhiệt (Mất khoảng 10-15 giây lần đầu tiên)...")

# ==========================================
# TAB 3: TOP 100 CỔ PHIẾU KHỐI LƯỢNG LỚN NHẤT
# ==========================================
with tab3:
    if not df_market.empty:
        st.markdown("### 📊 Biến động 100 cổ phiếu có thanh khoản lớn nhất")
        
        # Sắp xếp theo Khối lượng giảm dần và lấy Top 100
        df_top100 = df_market.sort_values(by='Tổng KL', ascending=False).head(100)
        
        # Hàm tô màu xanh đỏ cho Dataframe
        def color_change(val):
            if pd.isna(val): return ''
            if val > 0: return 'color: #00e676; font-weight: bold;'
            elif val < 0: return 'color: #ff4d4d; font-weight: bold;'
            else: return 'color: #f5b041; font-weight: bold;' # Màu vàng cho giá tham chiếu
            
        # Định dạng hiển thị số
        format_dict = {
            'Giá': '{:,.2f}',
            '+/-': '{:+,.2f}',
            '%': '{:+,.2f}%',
            'Tổng KL': '{:,.0f}'
        }
        
        # Áp dụng định dạng và tô màu
        # Dùng .applymap cho Pandas < 2.1, nếu lỗi bạn có thể đổi thành .map
        try:
            styled_df = df_top100.style.format(format_dict).map(color_change, subset=['+/-', '%'])
        except:
            styled_df = df_top100.style.format(format_dict).applymap(color_change, subset=['+/-', '%'])
        
        # Hiển thị bảng
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)
    else:
        st.info("⏳ Đang tải dữ liệu Bảng điện...")

# Tự động làm mới trang sau 60 giây
time.sleep(60)
st.rerun()
