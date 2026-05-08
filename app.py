import streamlit as st
import pandas as pd
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import pytz
import time

# 1. Cài đặt giao diện trang web
st.set_page_config(page_title="Fairy Invest - Realtime", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST - Thị trường chứng khoán (Real-time)")
st.markdown("Dữ liệu chỉ số VN-INDEX cập nhật tự động **mỗi phút** trong giờ giao dịch.")

# 2. Thiết lập thời gian (Ép múi giờ Việt Nam)
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
current_time = datetime.now(vn_tz)
end_date = current_time.strftime('%Y-%m-%d')
# Lấy dữ liệu 2 ngày gần nhất thôi, vì dữ liệu 1 phút rất nặng, lấy 30 ngày sẽ bị lỗi
start_date = (current_time - timedelta(days=2)).strftime('%Y-%m-%d')

# Cache dữ liệu trong 60 giây để tránh bị nhà cung cấp chặn API vì gọi quá nhiều
@st.cache_data(ttl=60) 
def get_realtime_data():
    # CHÚ Ý: resolution='1' để lấy dữ liệu từng phút
    df = stock_historical_data(symbol='VNINDEX', start_date=start_date, end_date=end_date, resolution='1', type='index')
    return df

try:
    df_index = get_realtime_data()
    
    if not df_index.empty:
        # Lấy dòng dữ liệu mới nhất (hiện tại) và dòng ngay trước đó (cách 1 phút)
        latest_data = df_index.iloc[-1]
        prev_data = df_index.iloc[-2]
        
        # Tính toán mức thay đổi theo phút
        current_score = latest_data['close']
        point_change = current_score - prev_data['close']
        
        # Hiển thị thời gian cập nhật cuối cùng
        last_update_str = latest_data['time']
        
        # 3. Hiển thị thẻ chỉ số (Metric)
        st.metric(
            label=f"VN-INDEX (Cập nhật lúc: {last_update_str})", 
            value=f"{current_score:,.2f}", 
            delta=f"{point_change:,.2f} điểm (so với phút trước)"
        )
        
        st.divider() # Đường kẻ ngang
        
        # 4. Hiển thị biểu đồ Real-time
        st.subheader("📈 Biểu đồ biến động Real-time (Khung 1 Phút)")
        chart_data = df_index[['time', 'close']].set_index('time')
        st.line_chart(chart_data)
        
        # 5. Bảng dữ liệu chi tiết
        with st.expander("Xem chi tiết dòng thời gian"):
            # Đảo ngược bảng để xem dữ liệu mới nhất ở trên cùng
            st.dataframe(
                df_index[['time', 'open', 'high', 'low', 'close', 'volume']].iloc[::-1], 
                use_container_width=True,
                hide_index=True
            )
            
    else:
        st.warning("Đang chờ kết nối dữ liệu...")

except Exception as e:
    st.error(f"Có lỗi xảy ra khi lấy dữ liệu: {e}")

# 6. Vòng lặp tự động làm mới trang (Auto-refresh)
# Chờ 60 giây sau đó tự động tải lại web
time.sleep(60)
st.rerun()
