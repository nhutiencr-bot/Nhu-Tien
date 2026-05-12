import streamlit as st

def apply_custom_css():
    st.markdown("""
    <style>
        div[data-testid='stMetric'] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
        .card { background: #1e1e2f; padding: 20px; border-radius: 10px; color: white; border-left: 5px solid #00e5ff; margin-bottom: 15px; }
        .scenario-box { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
    </style>
    """, unsafe_allow_html=True)

def render_ai_vsa_card(c, ma, v, vma, adv, dec):
    # Đổi khối lượng ra đơn vị Triệu Cổ Phiếu
    v_mil = v / 1000000      
    vma_mil = vma / 1000000  
    
    # 1. AI Đọc vị Dòng tiền Real-time (Chuẩn VSA)
    if v > vma:
        if c > ma: 
            vol_msg = f"Dòng tiền <b style='color:#00e676;'>MUA CHỦ ĐỘNG</b> rất mạnh (Đạt {v_mil:,.1f} triệu CP, vượt mức trung bình {vma_mil:,.1f} triệu CP)."
        else: 
            vol_msg = f"Áp lực <b style='color:#ff4d4d;'>BÁN THÁO</b> cực lớn (Đạt {v_mil:,.1f} triệu CP, vượt mức trung bình {vma_mil:,.1f} triệu CP)."
    else:
        if c > ma: 
            vol_msg = f"Tăng điểm nhưng Thanh khoản <b style='color:#f5b041;'>THẤP</b> (Đạt {v_mil:,.1f} triệu CP, dưới mức trung bình {vma_mil:,.1f} triệu CP). Lực cầu dè dặt."
        else: 
            vol_msg = f"Thanh khoản <b style='color:#ff4d4d;'>SUY YẾU</b> (Đạt {v_mil:,.1f} triệu CP, thấp hơn mức trung bình {vma_mil:,.1f} triệu CP). Dòng tiền lớn đang đứng ngoài."

    # 2. Xuất giao diện AI Card
    st.markdown(f"""
    <div class='card'>
        <h3 style='margin-top:0; color:#00e5ff;'>🤖 ĐÁNH GIÁ HỆ THỐNG VSA (REAL-TIME)</h3>
        <p style='font-size: 16px;'>• <b>Hành động giá:</b> VN-INDEX đang ở mức {c:,.2f} ({'<b style="color:#00e676;">Nằm TRÊN</b>' if c > ma else '<b style="color:#ff4d4d;">Rơi XUỐNG DƯỚI</b>'} MA20).</p>
        <p style='font-size: 16px;'>• <b>Thanh khoản:</b> {vol_msg}</p>
        <p style='font-size: 16px;'>• <b>Độ rộng thị trường:</b> Có {adv} mã Tăng / {dec} mã Giảm.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 3. Xuất Kịch Bản kết hợp Điểm số
    score = sum([c > ma, v > vma, adv > dec])
    
    if score >= 2:
        st.success(f"🟢 **KỊCH BẢN TÍCH CỰC:**\n\nSự lan tỏa đang diễn ra cực tốt. Hành động: Ưu tiên nắm giữ, gia tăng tỷ trọng và mở mua mới ở các mã có nền giá.")
    elif score == 1:
        st.warning(f"🟡 **KỊCH BẢN GIẰNG CO:**\n\nTrạng thái phân hóa mạnh, có hiện tượng kéo trụ. Hành động: Duy trì tỷ trọng cân bằng 50/50, chỉ mua bán chọn lọc, không FOMO giá xanh.")
    else:
        st.error(f"🔴 **KỊCH BẢN RỦI RO:**\n\nÁp lực bán áp đảo, thị trường mất vùng hỗ trợ. Hành động: Quản trị rủi ro tuyệt đối, kiên quyết hạ Margin và đứng ngoài thị trường.")
