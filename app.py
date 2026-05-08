import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import time
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures

# 1. CÀI ĐẶT GIAO DIỆN
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Dashboard Chứng Khoán")

# 2. THIẾT LẬP THỜI GIAN
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
start_date_stock = (current_time - timedelta(days=7)).strftime('%Y-%m-%d')
start_date_index = (current_time - timedelta(days=5)).strftime('%Y-%m-%d')

# 3. HÀM QUÉT TOÀN THỊ TRƯỜNG VÀ TÌM TOP 100 
@st.cache_data(ttl=86400)
def get_company_sectors():
    try:
        df = listing_companies()
        hose_df = df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)]
        return hose_df[['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except:
        return {}

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
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_ticker, t) for t in tickers]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['Tổng KL'] > 0:
                results.append(res)
                
    df_market = pd.DataFrame(results)
    if not df_market.empty:
        df_market = df_market.sort_values(by='Tổng KL', ascending=False).head(100)
    return df_market

# 4. TẠO GIAO DIỆN 3 TABS
tab1, tab2, tab3 = st.tabs(["📈 VN-INDEX", "🗺️ Bản đồ dòng tiền", "📊 Top 100 Active"])

# ==========================================
# TAB 1: VN-INDEX REALTIME & THANH KHOẢN
# ==========================================
with tab1:
    @st.cache_data(ttl=60)
    def get_realtime_index():
        return stock_historical_data(symbol='VNINDEX', start_date=start_date_index, end_date=end_date, resolution='1', type='index')

    try:
        df_index = get_realtime_index()
        
        if not df_index.empty:
            df_index['date'] = pd.to_datetime(df_index['time']).dt.date
            unique_dates = df_index['date'].unique()
            
            if len(unique_dates) >= 2:
                today_date = unique_dates[-1]
                yest_date = unique_dates[-2]
                
                df_today = df_index[df_index['date'] == today_date].copy()
                df_yest = df_index[df_index['date'] == yest_date].copy()
                
                # --- XỬ LÝ CHỈ SỐ ĐIỂM ---
                current_score = df_today.iloc[-1]['close']
                latest_time = df_today.iloc[-1]['time']
                ref_price = df_yest.iloc[-1]['close']
                
                point_change = current_score - ref_price
                pct_change = (point_change / ref_price) * 100
                
                st.metric(
                    label=f"VN-INDEX (Cập nhật lúc: {latest_time})", 
                    value=f"{current_score:,.2f}", 
                    delta=f"{point_change:+,.2f} điểm ({pct_change:+,.2f}%)"
                )
                
                st.divider()
                
                # --- VẼ BIỂU ĐỒ THANH KHOẢN SO SÁNH ---
                st.markdown("### 🌊 Biểu đồ Thanh khoản (Hôm nay vs Hôm qua)")
                
                df_today['time_str'] = pd.to_datetime(df_today['time']).dt.strftime('%H:%M')
                df_yest['time_str'] = pd.to_datetime(df_yest['time']).dt.strftime('%H:%M')
                
                df_today['cum_vol'] = df_today['volume'].cumsum()
                df_yest['cum_vol'] = df_yest['volume'].cumsum()
                
                fig_liq = go.Figure()
                
                fig_liq.add_trace(go.Scatter(
                    x=df_yest['time_str'], y=df_yest['cum_vol'],
                    fill='tozeroy', mode='lines',
                    name=f'Hôm qua ({yest_date.strftime("%d/%m")})',
                    line=dict(color='rgba(65, 105, 225, 0.6)', width=2),
                    fillcolor='rgba(65, 105, 225, 0.1)'
                ))
                
                fig_liq.add_trace(go.Scatter(
                    x=df_today['time_str'], y=df_today['cum_vol'],
                    fill='tozeroy', mode='lines',
                    name=f'Hôm nay ({today_date.strftime("%d/%m")})',
                    line=dict(color='rgba(154, 205, 50, 0.9)', width=2),
                    fillcolor='rgba(154, 205, 50, 0.5)'
                ))
                
                fig_liq.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=450,
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_liq, use_container_width=True)
                
                with st.expander("Xem biểu đồ điểm số VN-INDEX trong ngày"):
                    st.line_chart(df_today[['time_str', 'close']].set_index('time_str'))

    except Exception as e:
        st.error("Đang chờ dữ liệu VN-INDEX...")

# TẢI DỮ LIỆU TOP 100 CHUNG CHO TAB 2 & 3
df_top100 = get_dynamic_top_100()

# ==========================================
# TAB 2: BẢN ĐỒ NHIỆT (HEATMAP DÒNG TIỀN)
# ==========================================
with tab2:
    if not df_top100.empty:
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
