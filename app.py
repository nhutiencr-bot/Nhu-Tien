import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api_helpers import get_top_100, get_idx_live, get_index_contrib
from utils.ui_components import apply_global_css, style_dataframe, MAP_COLORS, C_GREEN, C_RED

st.set_page_config(page_title="Trang Chủ | Fairy Invest", page_icon="🧚‍♀️", layout="wide")
apply_global_css()
st.title("🧚‍♀️ FAIRY INVEST - Tổng Quan Thị Trường")

with st.spinner("Đang tải dữ liệu..."):
    df_100, df_idx, df_c = get_top_100(), get_idx_live(), get_index_contrib()

t1, t2, t3 = st.tabs(["📈 VN-INDEX & Tác động", "🗺️ Bản đồ Dòng tiền", "📊 Top 100 Giao Dịch"])

with t1:
    if not df_idx.empty:
        df_idx['date'] = pd.to_datetime(df_idx['time']).dt.date
        dates = df_idx['date'].unique()
        if len(dates) >= 2:
            dt_t, dt_y = df_idx[df_idx['date'] == dates[-1]].copy(), df_idx[df_idx['date'] == dates[-2]].copy()
            c, p = dt_t.iloc[-1]['close'], dt_y.iloc[-1]['close']
            st.metric(f"VN-INDEX (Lúc {dt_t.iloc[-1]['time']})", f"{c:,.2f}", f"{c-p:+,.2f} ({(c-p)/p*100:+,.2f}%)")
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🌊 Thanh khoản")
                dt_t['ts'], dt_y['ts'] = pd.to_datetime(dt_t['time']).dt.strftime('%H:%M'), pd.to_datetime(dt_y['time']).dt.strftime('%H:%M')
                dt_t['cum'], dt_y['cum'] = dt_t['volume'].cumsum(), dt_y['volume'].cumsum()
                fig_liq = go.Figure()
                fig_liq.add_trace(go.Scatter(x=dt_y['ts'], y=dt_y['cum'], fill='tozeroy', name='Hôm qua', line=dict(color='rgba(150,150,150,0.5)')))
                fig_liq.add_trace(go.Scatter(x=dt_t['ts'], y=dt_t['cum'], fill='tozeroy', name='Hôm nay', line=dict(color='#00e676')))
                st.plotly_chart(fig_liq.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350, legend=dict(y=1.1, orientation="h")), use_container_width=True)

            with c2:
                st.markdown("#### 🎯 Tác động điểm số")
                if not df_c.empty:
                    res = pd.concat([df_c[df_c['Điểm']>0].nlargest(7, 'Điểm'), df_c[df_c['Điểm']<0].nsmallest(7, 'Điểm')]).sort_values('Điểm', ascending=False)
                    fig_b = go.Figure(go.Bar(x=res['Mã CK'], y=res['Điểm'], marker_color=[C_GREEN if v > 0 else C_RED for v in res['Điểm']], text=res['Điểm'].apply(lambda x: f"{x:+.2f}"), textposition='outside'))
                    st.plotly_chart(fig_b.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350), use_container_width=True)

with t2:
    if not df_100.empty:
        fig = px.treemap(df_100, path=[px.Constant("Thị trường"), 'Nhóm Ngành', 'Mã CK'], values='Tổng KL', color='%', color_continuous_scale=MAP_COLORS, range_color=[-7, 7], custom_data=['%', 'Tổng KL'])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]:+.2f}%", textposition="middle center")
        st.plotly_chart(fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=600), use_container_width=True)

with t3:
    if not df_100.empty:
        st.dataframe(df_100.style.format({'Giá': '{:,.2f}', '+/-': '{:+,.2f}', '%': '{:+,.2f}%', 'Tổng KL': '{:,.0f}'}).map(style_dataframe, subset=['+/-', '%']), use_container_width=True, hide_index=True, height=600)
