import streamlit as st

# MÀU SẮC CHUẨN
C_CEIL, C_GREEN, C_REF = '#cc00ff', '#00e676', '#f5b041'
C_RED, C_DRED, C_FLOOR = '#ff4d4d', '#b30000', '#00e5ff'

MAP_COLORS = [
    [0.0, C_FLOOR], [0.014, C_FLOOR], [0.014, C_DRED], [0.285, C_DRED],
    [0.285, C_RED], [0.499, C_RED], [0.499, C_REF], [0.501, C_REF],
    [0.501, C_GREEN], [0.985, C_GREEN], [0.985, C_CEIL], [1.0, C_CEIL]
]

def apply_global_css():
    st.markdown("""
    <style>
        div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 15px; }
        div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
        .card { background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%); padding: 20px; border-radius: 10px; color: white; border-left: 5px solid #00e5ff; margin-bottom: 15px; }
        .scenario-box { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
    </style>
    """, unsafe_allow_html=True)

def style_dataframe(v):
    try:
        v = float(v)
        if v >= 6.8: return f'color: {C_CEIL}; font-weight: bold;'
        elif v <= -6.8: return f'color: {C_FLOOR}; font-weight: bold;'
        elif v > 0: return f'color: {C_GREEN}; font-weight: bold;'
        elif v == 0: return f'color: {C_REF}; font-weight: bold;'
        elif v > -3: return f'color: {C_RED}; font-weight: bold;'
        else: return f'color: {C_DRED}; font-weight: bold;'
    except: return ''

def render_ai_vsa_card(c, ma, v, vma, adv, dec):
    v_mil, vma_mil = v / 1e6, vma / 1e6
    if v > vma:
        if c > ma: vol_msg, kl_col = f"Dòng tiền <b style='color:#00e676;'>MUA CHỦ ĐỘNG</b> rất mạnh (Đạt {v_mil:,.1f} Tr CP, vượt TB {vma_mil:,.1f} Tr CP).", C_GREEN
        else: vol_msg, kl_col = f"Áp lực <b style='color:#ff4d4d;'>BÁN THÁO</b> cực lớn (Đạt {v_mil:,.1f} Tr CP, vượt TB {vma_mil:,.1f} Tr CP).", C_RED
    else:
        if c > ma: vol_msg, kl_col = f"Thanh khoản <b style='color:#f5b041;'>THẤP</b> (Đạt {v_mil:,.1f} Tr CP, dưới TB {vma_mil:,.1f} Tr CP). Lực cầu dè dặt.", C_REF
        else: vol_msg, kl_col = f"Thanh khoản <b style='color:#ff4d4d;'>SUY YẾU</b> (Đạt {v_mil:,.1f} Tr CP, dưới TB {vma_mil:,.1f} Tr CP). Cầu trống rỗng.", C_RED

    if adv > dec * 1.5: rong_msg, rong_col = f"LAN TỎA TÍCH CỰC ({adv} Tăng / {dec} Giảm). Sắc xanh áp đảo.", C_GREEN
    elif dec > adv * 1.5: rong_msg, rong_col = f"CẢNH BÁO RỦI RO ({adv} Tăng / {dec} Giảm). Xanh vỏ đỏ lòng.", C_RED
    else: rong_msg, rong_col = f"GIẰNG CO PHÂN HÓA ({adv} Tăng / {dec} Giảm).", C_REF

    st.markdown(f"""
    <div class='card'>
        <h2 style='color:#00e5ff; margin-top:0;'>🤖 AI ĐÁNH GIÁ (REAL-TIME)</h2>
        <ul style='font-size: 17px; line-height: 1.8;'>
            <li><b>Khối lượng:</b> {vol_msg}</li>
            <li><b>Độ rộng:</b> <b style='color:{rong_col}'>{rong_msg}</b></li>
            <li><b>Giá:</b> VN-INDEX đang <b style='color:{"#00e676" if c > ma else "#ff4d4d"}'>{'NẰM TRÊN' if c > ma else 'DƯỚI'}</b> MA20 ({ma:,.2f}).</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    score = sum([c > ma, v > vma, adv > dec])
    if score >= 2: sc_col, sc_ti, sc_de = C_GREEN, "🟢 Kịch Bản Tích Cực", "Sự lan tỏa diễn ra tốt. Ưu tiên nắm giữ, gia tăng tỷ trọng mã có nền giá."
    elif score == 1: sc_col, sc_ti, sc_de = C_REF, "🟡 Kịch Bản Đi Ngang", "Trạng thái phân hóa mạnh. Duy trì tỷ trọng 50/50, mua bán chọn lọc."
    else: sc_col, sc_ti, sc_de = C_RED, "🔴 Kịch Bản Rủi Ro", "Áp lực bán lớn, mất hỗ trợ. Quản trị rủi ro tuyệt đối, kiên quyết hạ Margin."

    st.markdown(f"<div class='scenario-box' style='border-left: 5px solid {sc_col};'><h3 style='color:{sc_col}; margin-top:0;'>{sc_ti}</h3><p style='font-size:16px;'>{sc_de}</p></div>", unsafe_allow_html=True)
