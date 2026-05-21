def update_dataframe_to_sheet(sheet_name, df, worksheet_index=0):
    """
    Hàm đẩy toàn bộ dữ liệu từ DataFrame lên Google Sheet
    """
    try:
        client = get_sheet_client()
        # Mở file Sheet theo tên và chọn trang tính
        sheet = client.open(sheet_name).get_worksheet(worksheet_index)
        
        # Xóa toàn bộ dữ liệu cũ trên trang tính
        sheet.clear()
        
        # Chuyển đổi DataFrame thành dạng List of Lists
        data_to_upload = [df.columns.values.tolist()] + df.values.tolist()
        
        # Đẩy dữ liệu lên bắt đầu từ ô A1
        sheet.update(values=data_to_upload, range_name='A1')
        return True, "Thành công"
        
    except Exception as e:
        # Trả về False và nội dung lỗi để hiển thị lên Streamlit
        return False, str(e)
