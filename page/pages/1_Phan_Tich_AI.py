import streamlit as st
import pandas as pd
import re
from utils.api_helpers import fetch_proxy, get_vnindex_ma
from utils.ui_components import apply_custom_css, render_ai_vsa_card

st.set_page_config(page_title="AI & Khuyến Nghị", layout="wide")
apply_custom_css()
st.title("🔮 CẬP NHẬT KHUYẾN NGHỊ & AI (VSA)")

@st.cache_data(ttl=900)
def get_cafef():
    html = fetch_proxy("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30")
    res = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b)
            l_m = re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                title = t_m.group(1).strip()
                tk = (re.search(r'\b([A-Z]{3})\b', title) or re.search('','')).group(0)
                res.append({"Mã": tk, "Nội dung": title, "Link": "https://s.cafef.vn" + l_m.group(1)})
    return pd.DataFrame(res)

t1, t2 = st.tabs(["📝 Khuyến nghị CafeF", "📊 Phân tích AI VSA"])

with t1:
    df_rep = get_cafef()
    if not df_rep.empty: st.dataframe(df_rep, use_container_width=True, hide_index=True)
    else: st.warning("Đang kết nối kho báo cáo...")

with t2:
    df_idx = get_vnindex_ma()
    if not df_idx.empty:
        c, ma = df_idx.iloc[-1]['close'], df_idx.iloc[-1]['MA20']
        v, vma = df_idx.iloc[-1]['volume'], df_idx.iloc[-1]['VMA20']
        render_ai_vsa_card(c, ma, v, vma)
        st.line_chart(df_idx.set_index('time')[['close', 'MA20']])
