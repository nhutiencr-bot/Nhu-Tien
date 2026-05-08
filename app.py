import streamlit as st
import pandas as pd
# CẬP NHẬT: Sử dụng thư viện vnstock mới nhất (vnstock3)
from vnstock import Vnstock

# --- CẤU HÌNH TRANG STREAMLIT ---
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")
st.title("🧚‍♀️ FAIRY INVEST")

# --- MÔ TẢ YÊU CẦU ---
st.markdown("### Danh sách cổ phiếu đóng góp điểm số VN-INDEX")
st.markdown("*Dữ liệu được cập nhật (gần) Real-time, lọc Top mã biến động mạnh.*")

# Khởi tạo vnstock
vn = Vnstock()

# --- HÀM LẤY DỮ LIỆU ĐÓNG GÓP (MỚI TỪ VNSTOCK3) ---
@st.cache_data(ttl=60) # Lưu cache 60 giây (gần Real-time)
def get_stock_contribution(index='VNINDEX'):
    try:
        # vnstock3: lấy danh sách các mã tác động chỉ số
        df = vn.market_watch.tickers_contrib_index(index=index, limit=20)
        return df
    except Exception as e:
        return pd.DataFrame() # Trả về DataFrame rỗng nếu lỗi API

# --- NÚT LÀM MỚI ---
if st.button("🔄 Làm mới dữ liệu (Gần Real-time)"):
    st.cache_data.clear() # Xóa cache cũ để Streamlit tải lại dữ liệu mới

# --- LẤY VÀ HIỂN THỊ DỮ LIỆU ---
st.info("⏳ Đang tải dữ liệu đóng góp điểm số...")
df_raw = get_stock_contribution()

if not df_raw.empty:
    st.cache_data.clear() # Clear info message if data loads
    st.success("✅ Đã tải dữ liệu đóng góp điểm số.")

    # --- SƠ CHẾ DỮ LIỆU ĐỂ GIỐNG ẢNH MẪU CỦA BẠN ---
    # Ảnh mẫu của bạn cần 2 cột: Mã Cổ Phiếu, Điểm Số Đóng Góp.
    # vnstock3 thường trả về các cột: Symbol (Mã), PriceChangePercent (%), Volume (KL), Contrib_point (Điểm tác động)

    # 1. Tách danh sách Top Tăng và Top Giảm
    df_pos = df_raw[df_raw['Contrib_point'] > 0].sort_values(by='Contrib_point', ascending=False).head(10)
    df_neg = df_raw[df_raw['Contrib_point'] < 0].sort_values(by='Contrib_point', ascending=True).head(10)

    # 2. Tạo giao diện 2 cột
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ✅ Cổ phiếu KÉO TĂNG Index")
        st.dataframe(
            df_pos[['Symbol', 'Contrib_point']],
            column_config={
                "Symbol": "Mã CP",
                "Contrib_point": "Điểm số đóng góp"
            },
            use_container_width=True,
            hide_index=True
        )

    with col2:
        st.markdown("#### ❌ Cổ phiếu KÉO GIẢM Index")
        st.dataframe(
            df_neg[['Symbol', 'Contrib_point']],
            column_config={
                "Symbol": "Mã CP",
                "Contrib_point": "Điểm số đóng góp"
            },
            use_container_width=True,
            hide_index=True
        )

else:
    st.error("❌ Không thể lấy dữ liệu đóng góp điểm số. Vui lòng:")
    st.error("1. Đảm bảo file `requirements.txt` không còn dòng `vnstock==0.2.9.2.2`. (Hãy dùng phiên bản vnstock mới nhất).")
    st.error("2. Kiểm tra lại kết nối mạng trên server Streamlit.")
