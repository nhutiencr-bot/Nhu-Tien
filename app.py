# ==========================================
# TAB 5: 📡 AI PHÂN TÍCH — CLAUDE API
# ==========================================
with t5:
    st.markdown("### 📡 AI Phân Tích Thị Trường")
    st.caption("Nhập các thông số phiên giao dịch, AI sẽ dự báo kịch bản và xác suất xu hướng.")

    # --- INPUT API KEY ---
    with st.expander("🔑 Cấu hình Claude API Key", expanded=False):
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Lấy tại https://console.anthropic.com"
        )

    st.divider()

    # --- INPUT THÔNG SỐ THỊ TRƯỜNG ---
    st.markdown("#### 📥 Nhập thông số phiên hôm nay")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        # Tự động điền nếu đã có dữ liệu
        default_vol = 750
        default_vnindex = 1250.0
        if not df_100.empty:
            default_vol = int(df_100['Tổng KL'].sum() / 1_000_000)

        vol_input = st.number_input(
            "💧 Thanh khoản thị trường (tỷ đồng)",
            min_value=100, max_value=3000,
            value=default_vol,
            step=50,
            help="Tổng giá trị khớp lệnh toàn thị trường"
        )

        # Slider kịch bản volume
        st.markdown("**Thử kịch bản volume:**")
        vol_scenario = st.slider(
            "Kéo để xem kịch bản",
            min_value=300, max_value=2000,
            value=vol_input, step=50,
            label_visibility="collapsed"
        )

    with col_b:
        try:
            df_daily_ai = stock_historical_data('VNINDEX', start_index, end_date, '1D', 'index')
            if df_daily_ai is not None and not df_daily_ai.empty:
                df_daily_ai = df_daily_ai.dropna(subset=['close'])
                default_vnindex = float(df_daily_ai.iloc[-1]['close'])
                default_ref = float(df_daily_ai.iloc[-2]['close']) if len(df_daily_ai) >= 2 else default_vnindex
            else:
                default_ref = default_vnindex
        except:
            default_ref = default_vnindex

        vnindex_input = st.number_input(
            "📊 Điểm VN-INDEX hiện tại",
            min_value=500.0, max_value=2000.0,
            value=default_vnindex,
            step=0.5,
            format="%.2f"
        )
        ref_input = st.number_input(
            "📌 Điểm tham chiếu (phiên trước)",
            min_value=500.0, max_value=2000.0,
            value=default_ref,
            step=0.5,
            format="%.2f"
        )

    with col_c:
        # Tự động tính breadth từ df_100
        default_advance = 50
        default_decline = 30
        default_nochange = 20
        if not df_100.empty:
            default_advance = int((df_100['%'] > 0).sum())
            default_decline = int((df_100['%'] < 0).sum())
            default_nochange = int((df_100['%'] == 0).sum())

        advance_input = st.number_input("📈 Số mã tăng giá", min_value=0, max_value=800, value=default_advance)
        decline_input = st.number_input("📉 Số mã giảm giá", min_value=0, max_value=800, value=default_decline)
        nochange_input = st.number_input("➡️ Số mã đứng giá", min_value=0, max_value=800, value=default_nochange)

    # Top movers từ df_100
    top_gainers_str = "N/A"
    top_losers_str = "N/A"
    if not df_100.empty:
        top_g = df_100.nlargest(5, '%')[['Mã CK', '%']].apply(lambda r: f"{r['Mã CK']}({r['%']:+.1f}%)", axis=1).tolist()
        top_l = df_100.nsmallest(5, '%')[['Mã CK', '%']].apply(lambda r: f"{r['Mã CK']}({r['%']:+.1f}%)", axis=1).tolist()
        top_gainers_str = ", ".join(top_g)
        top_losers_str = ", ".join(top_l)

    st.divider()

    # --- NÚT PHÂN TÍCH ---
    run_ai = st.button("🚀 Chạy AI Phân Tích", type="primary", use_container_width=True)

    if run_ai:
        if not api_key or not api_key.startswith("sk-ant"):
            st.error("❌ Vui lòng nhập đúng Anthropic API Key ở phần cấu hình bên trên.")
        else:
            delta_pts = vnindex_input - ref_input
            delta_pct = (delta_pts / ref_input * 100) if ref_input != 0 else 0
            total_stocks = advance_input + decline_input + nochange_input
            breadth_ratio = (advance_input / total_stocks * 100) if total_stocks > 0 else 50

            # Phân loại volume tự động
            if vol_scenario <= 500:
                vol_label = "rất thấp (thị trường thiếu động lực)"
            elif vol_scenario <= 700:
                vol_label = "thấp (dưới mức trung bình)"
            elif vol_scenario <= 900:
                vol_label = "trung bình (bình thường)"
            elif vol_scenario <= 1200:
                vol_label = "tốt (trên trung bình, dòng tiền vào)"
            else:
                vol_label = "rất cao (dòng tiền mạnh hoặc panic)"

            prompt = f"""Bạn là chuyên gia phân tích kỹ thuật thị trường chứng khoán Việt Nam (HOSE).

Dưới đây là dữ liệu thực tế phiên giao dịch hôm nay:

**THÔNG SỐ THỊ TRƯỜNG:**
- VN-INDEX hiện tại: {vnindex_input:,.2f} điểm
- Điểm tham chiếu phiên trước: {ref_input:,.2f} điểm
- Thay đổi hiện tại: {delta_pts:+.2f} điểm ({delta_pct:+.2f}%)
- Thanh khoản thực tế: {vol_input:,} tỷ đồng
- **Kịch bản volume đang xét: {vol_scenario:,} tỷ đồng** ({vol_label})
- Số mã tăng / giảm / đứng: {advance_input} / {decline_input} / {nochange_input}
- Tỷ lệ breadth (% mã tăng): {breadth_ratio:.1f}%
- Top 5 cổ phiếu tăng mạnh nhất: {top_gainers_str}
- Top 5 cổ phiếu giảm mạnh nhất: {top_losers_str}

**YÊU CẦU PHÂN TÍCH:**
Dựa trên dữ liệu trên, hãy phân tích và đưa ra:

1. **ĐÁNH GIÁ TỔNG QUAN** (2-3 câu nhận xét sức mạnh thị trường)

2. **3 KỊCH BẢN CUỐI PHIÊN** với format chính xác như sau:
   - 🐂 BULL (Tăng): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]
   - 🦀 BASE (Sideway): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]  
   - 🐻 BEAR (Giảm): Xác suất X% — VN-INDEX dự báo: [điểm thấp]-[điểm cao] — Điều kiện: [mô tả]
   (3 xác suất phải cộng = 100%)

3. **TÁC ĐỘNG CỦA VOLUME {vol_scenario:,} TỶ**: Nếu thanh khoản đạt mức này so với thực tế {vol_input:,} tỷ thì thị trường sẽ như thế nào? Tăng/giảm bao nhiêu điểm?

4. **KHUYẾN NGHỊ CHIẾN LƯỢC** (ngắn gọn cho nhà đầu tư ngắn hạn)

Trả lời bằng tiếng Việt, rõ ràng, chuyên nghiệp, có số liệu cụ thể."""

            with st.spinner("🤖 Claude đang phân tích thị trường..."):
                try:
                    import json
                    response = requests.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-opus-4-5",
                            "max_tokens": 1500,
                            "messages": [{"role": "user", "content": prompt}]
                        },
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        ai_text = result['content'][0]['text']

                        # --- HIỂN THỊ KẾT QUẢ ---
                        st.success("✅ Phân tích hoàn tất!")
                        st.divider()

                        # Parse xác suất để vẽ gauge
                        import re as re2
                        bull_match = re2.search(r'BULL.*?(\d+)%', ai_text)
                        base_match = re2.search(r'BASE.*?(\d+)%', ai_text)
                        bear_match = re2.search(r'BEAR.*?(\d+)%', ai_text)

                        bull_pct = int(bull_match.group(1)) if bull_match else 33
                        base_pct = int(base_match.group(1)) if base_match else 34
                        bear_pct = int(bear_match.group(1)) if bear_match else 33

                        # Gauge xác suất
                        col_g1, col_g2, col_g3 = st.columns(3)
                        for col, label, pct, color, emoji in [
                            (col_g1, "BULL 🐂", bull_pct, "#00e676", "📈"),
                            (col_g2, "BASE 🦀", base_pct, "#f5b041", "➡️"),
                            (col_g3, "BEAR 🐻", bear_pct, "#ff4d4d", "📉")
                        ]:
                            with col:
                                fig_gauge = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=pct,
                                    number={'suffix': "%", 'font': {'size': 36, 'color': color}},
                                    title={'text': label, 'font': {'size': 16}},
                                    gauge={
                                        'axis': {'range': [0, 100], 'tickwidth': 1},
                                        'bar': {'color': color},
                                        'bgcolor': "rgba(0,0,0,0)",
                                        'steps': [
                                            {'range': [0, 30], 'color': 'rgba(255,255,255,0.05)'},
                                            {'range': [30, 70], 'color': 'rgba(255,255,255,0.1)'},
                                            {'range': [70, 100], 'color': 'rgba(255,255,255,0.15)'}
                                        ],
                                        'threshold': {
                                            'line': {'color': color, 'width': 4},
                                            'thickness': 0.75,
                                            'value': pct
                                        }
                                    }
                                ))
                                fig_gauge.update_layout(
                                    height=220,
                                    margin=dict(l=20, r=20, t=40, b=10),
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font_color='white'
                                )
                                st.plotly_chart(fig_gauge, use_container_width=True)

                        st.divider()

                        # Nội dung phân tích đầy đủ
                        st.markdown("#### 📋 Phân Tích Chi Tiết")
                        st.markdown(ai_text)

                        # Volume impact bar chart
                        st.divider()
                        st.markdown("#### 💧 Tác Động Volume Theo Kịch Bản")
                        vol_levels = [400, 500, 600, 700, 800, 900, 1000, 1200, 1500]
                        # Rule-based estimate: mỗi 100 tỷ volume thêm ~ 0.3-0.5 điểm
                        base_pts = vnindex_input
                        vol_base = 700
                        impact = [(v, round(base_pts + (v - vol_base) * 0.004, 2)) for v in vol_levels]
                        df_vol = pd.DataFrame(impact, columns=['Volume (tỷ)', 'Dự báo VN-INDEX'])
                        df_vol['Màu'] = df_vol['Dự báo VN-INDEX'].apply(
                            lambda x: C_GREEN if x > base_pts else (C_RED if x < base_pts else C_REF)
                        )
                        fig_vol = go.Figure(go.Bar(
                            x=df_vol['Volume (tỷ)'].astype(str) + " tỷ",
                            y=df_vol['Dự báo VN-INDEX'],
                            marker_color=df_vol['Màu'],
                            text=df_vol['Dự báo VN-INDEX'].apply(lambda x: f"{x:,.2f}"),
                            textposition='outside'
                        ))
                        fig_vol.add_hline(y=base_pts, line_dash="dash", line_color=C_REF,
                                          annotation_text=f"Tham chiếu: {base_pts:,.2f}")
                        fig_vol.update_layout(
                            height=350,
                            margin=dict(l=10, r=10, t=30, b=10),
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis_title="Thanh khoản",
                            yaxis_title="Điểm VN-INDEX dự báo",
                            yaxis=dict(range=[base_pts - 5, base_pts + 5])
                        )
                        st.plotly_chart(fig_vol, use_container_width=True)

                    elif response.status_code == 401:
                        st.error("❌ API Key không hợp lệ. Kiểm tra lại tại console.anthropic.com")
                    elif response.status_code == 429:
                        st.error("⏳ Rate limit — thử lại sau 1 phút.")
                    else:
                        st.error(f"❌ Lỗi API: {response.status_code} — {response.text[:200]}")

                except requests.exceptions.Timeout:
                    st.error("⏱️ Timeout — Claude không phản hồi trong 30 giây. Thử lại.")
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")
    else:
        # Placeholder khi chưa chạy
        st.info("👆 Kiểm tra thông số và nhấn **Chạy AI Phân Tích** để bắt đầu.")
        col_hint1, col_hint2, col_hint3 = st.columns(3)
        with col_hint1:
            st.markdown("""
            **📊 Volume 700-800 tỷ**  
            Mức trung bình thị trường VN.  
            Thường cho tín hiệu sideway hoặc tăng nhẹ.
            """)
        with col_hint2:
            st.markdown("""
            **📊 Volume > 1,000 tỷ**  
            Dòng tiền mạnh vào thị trường.  
            Tăng xác suất breakout hoặc panic sell.
            """)
        with col_hint3:
            st.markdown("""
            **📊 Volume < 500 tỷ**  
            Thị trường thiếu thanh khoản.  
            Thường sideway, khó đoán chiều.
            """)
