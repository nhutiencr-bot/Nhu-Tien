import streamlit as st
import pandas as pd
from utils.api_helpers import get_top_100, get_vnindex_ma, get_idx_live, get_cafef_reports
from utils.ui_components import apply_global_css, render_ai_vsa_card, C_GREEN, C_RED, C_REF

st.set_page_config(page_title="AI Phân Tích | Fairy Invest", page_icon="🔮", layout="wide")
apply_global_css()
st.title("🔮 CẬP NHẬT KHUYẾN NGHỊ & AI VSA")

with st.spinner("Đang quét báo cáo và tính toán VSA..."):
    df_100, df_idx, df_ma, df_rep = get_top_100(), get_idx_live(), get_vnindex_ma(), get_cafef_reports()

t1, t2 = st.tabs(["📝 Khuyến nghị (CafeF)", "🤖 AI Nhận định (VSA)"])

with t1:
    if not df_rep.empty:
        st.dataframe(df_rep.style.map(lambda v: f'color: {C_GREEN if "MUA" in str(v) else C_RED if "BÁN" in str(v) else C_REF}; font-weight:bold;', subset=['Khuyến nghị']), column_config={"Link": st.column_config.LinkColumn("Tải PDF")}, hide_index=True, use_container_width=True, height=600)
    else: st.warning("Đang quét dữ liệu CafeF...")

with t2:
    if not df_ma.empty and not df_100.empty and not df_idx.empty:
        c, ma = df_idx.iloc[-1]['close'], df_ma.iloc[-1]['MA20']
        dt_last = df_idx['date'].unique()[-1]
        v, vma = df_idx[df_idx['date'] == dt_last]['volume'].sum(), df_ma.iloc[-1]['VMA20']
        adv, dec = len(df_100[df_100['%'] > 0]), len(df_100[df_100['%'] < 0])
        
        # Gọi hàm vẽ AI Card từ utils/ui_components
        render_ai_vsa_card(c, ma, v, vma, adv, dec)
