import streamlit as st

def apply_custom_css():
    st.markdown("""
    <style>
        .card { background: #1e1e2f; padding: 20px; border-radius: 10px; color: white; border-left: 5px solid #00e5ff; }
        .scenario { padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1); }
    </style>
    """, unsafe_allow_html=True)

def render_ai_vsa_card(c, ma, v, vma):
    vol_ratio = (v / vma) * 100 if vma > 0 else 0
    score = sum([c > ma, v > vma])
    
    st.markdown(f"""
    <div class='card'>
        <h3 style='margin-top:0;'>🤖 AI ĐÁNH GIÁ HỆ THỐNG (VSA)</h3>
        <p>• <b>Chỉ số:</b> {c:,.2f} ({'Nằm TRÊN' if c > ma else 'Nằm DƯỚI'} MA20)</p>
        <p>• <b>Thanh khoản:</b> {v/1e6:,.1f} Tr CP ({'Bùng nổ' if vol_ratio > 110 else 'Suy yếu'} - Đạt {vol_ratio:.1f}% TB)</p>
    </div>
    """, unsafe_allow_html=True)
    
    if score >= 2:
        st.success("🟢 KỊCH BẢN TÍCH CỰC: Dòng tiền lan tỏa mạnh. Ưu tiên gia tăng tỷ trọng.")
    elif score == 1:
        st.warning("🟡 KỊCH BẢN GIẰNG CO: Phân hóa diễn ra. Duy trì tỷ trọng cân bằng, mua bán chọn lọc.")
    else:
        st.error("🔴 KỊCH BẢN RỦI RO: Áp lực bán lớn, cầu suy yếu. Quản trị rủi ro tuyệt đối.")
