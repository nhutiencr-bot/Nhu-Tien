# --- KỊCH BẢN AI VSA (REAL-TIME) ---
        v_mil = v / 1000000      # Đổi khối lượng hiện tại ra Triệu CP
        vma_mil = vma / 1000000  # Đổi khối lượng MA20 ra Triệu CP
        
        # 1. AI Đọc vị Dòng tiền Real-time
        if v > vma:
            if c > ma:
                vol_msg = f"Dòng tiền MUA CHỦ ĐỘNG rất mạnh (Đạt {v_mil:,.1f} triệu CP, vượt mức trung bình {vma_mil:,.1f} triệu CP)."
            else:
                vol_msg = f"Áp lực BÁN THÁO cực lớn (Đạt {v_mil:,.1f} triệu CP, vượt mức trung bình {vma_mil:,.1f} triệu CP)."
        else:
            if c > ma:
                vol_msg = f"Tăng điểm nhưng Thanh khoản THẤP (Chỉ đạt {v_mil:,.1f} triệu CP, dưới mức trung bình {vma_mil:,.1f} triệu CP). Lực cầu dè dặt."
            else:
                vol_msg = f"Thanh khoản SUY YẾU (Chỉ đạt {v_mil:,.1f} triệu CP, thấp hơn mức trung bình {vma_mil:,.1f} triệu CP). Dòng tiền lớn đang đứng ngoài quan sát."

        # 2. Xuất Kịch Bản kết hợp Điểm số
        score = sum([c > ma, v > vma, adv > dec])
        
        if score >= 2:
            st.success(f"🟢 KỊCH BẢN TÍCH CỰC:\n\n{vol_msg} Sự lan tỏa đang diễn ra cực tốt. Hành động: Ưu tiên nắm giữ, gia tăng tỷ trọng và mở mua mới ở các mã có nền giá.")
        elif score == 1:
            st.warning(f"🟡 KỊCH BẢN GIẰNG CO:\n\n{vol_msg} Trạng thái phân hóa mạnh, có hiện tượng kéo trụ. Hành động: Duy trì tỷ trọng cân bằng 50/50, chỉ mua bán chọn lọc, không FOMO giá xanh.")
        else:
            st.error(f"🔴 KỊCH BẢN RỦI RO:\n\n{vol_msg} Áp lực bán áp đảo, thị trường mất vùng hỗ trợ. Hành động: Quản trị rủi ro tuyệt đối, kiên quyết hạ Margin và đứng ngoài thị trường.")
