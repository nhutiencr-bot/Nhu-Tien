import streamlit as st
# Nhớ import hàm mới từ file auto_update.py vào đầu file app.py của bạn
from auto_update import get_market_data_safe

# ... (các phần code khác của bạn) ...

# Lấy dữ liệu an toàn ngay trước khi dùng tới sidebar
df_100 = get_market_data_safe()

with st.sidebar:
    st.header("📑 Xuất Báo Cáo")
    st.write("Đồng bộ dữ liệu sang Google Sheets.")
    
    # ⚠️ ĐẢM BẢO CHỮ NÀY TRÙNG KHỚP 100% VỚI TÊN FILE GOOGLE SHEET CỦA BẠN
    TEN_FILE_SHEET = "Bao_Cao_Chung_Khoan_NhuTien" 
    
    if st.button("Lưu Top 100 KL lên Sheets", type="primary", use_container_width=True):
        if not df_100.empty and SHEET_API_READY:
            with st.spinner("Đang kết nối API và truyền dữ liệu..."):
                # Gọi hàm và lấy về trạng thái thành công hay thất bại
                success, message = update_dataframe_to_sheet(TEN_FILE_SHEET, df_100)
            
            if success:
                st.success(f"✅ {message} vào file: {TEN_FILE_SHEET}")
            else:
                # Hiển thị thông báo lỗi màu đỏ trực tiếp lên giao diện web
                st.error(f"❌ Lỗi kết nối Google Sheets: {message}")
                
        elif not SHEET_API_READY:
            st.error("Chưa kết nối được file google_sheet_api.py")
        else:
            st.warning("Dữ liệu Top 100 đang trống, thử lại sau.")
