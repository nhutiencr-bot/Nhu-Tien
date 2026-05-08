import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta

# 1. Cài đặt giao diện trang web
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Thị trường chứng khoán")
st.markdown("Dữ liệu chỉ số VN-INDEX cập nhật hàng ngày.")

# 2. Thiết lập thời gian (lấy dữ liệu 30 ngày gần nhất)
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

@st.cache_data(ttl=3600) # Lưu cache 1 tiếng để web chạy nhanh hơn
def get_market_data():
    # Lấy dữ liệu VNINDEX (chỉ định type='index')
    df = stock_historical_data(symbol='VNINDEX', start_date=start_date, end_date=end_date, resolution='1D', type='index')
    return df

try:
    df_index = get_market_data()
    
    if not df_index.empty:
        # Lấy dòng dữ liệu của ngày mới nhất và ngày liền kề trước đó
        latest_data = df_index.iloc[-1]
        prev_data = df_index.iloc[-2]
        
        # Tính toán mức thay đổi
        current_score = latest_data['close']
        point_change = current_score - prev_data['close']
        pct_change = (point_change / prev_data['close']) * 100
        
        # 3. Hiển thị thẻ chỉ số (Metric)
        st.metric(
            label=f"VN-INDEX ({latest_data['time']})", 
            value=f"{current_score:,.2f}", 
            delta=f"{point_change:,.2f} ({pct_change:.2f}%)"
        )
        
        st.divider() # Đường kẻ ngang
        
        # 4. Hiển thị biểu đồ
        st.subheader("📈 Biểu đồ biến động 30 ngày qua")
        # Định dạng lại dữ liệu để vẽ biểu đồ
        chart_data = df_index[['time', 'close']].set_index('time')
        st.line_chart(chart_data)
        
        # 5. Hiển thị bảng dữ liệu chi tiết
        st.subheader("📋 Bảng dữ liệu chi tiết")
        st.dataframe(
            df_index[['time', 'open', 'high', 'low', 'close', 'volume']], 
            use_container_width=True,
            hide_index=True
        )
        
    else:
        st.warning("Đang chờ cập nhật dữ liệu ngày hôm nay...")

except Exception as e:
    st.error(f"Có lỗi xảy ra khi lấy dữ liệu: {e}")
