@st.cache_data(ttl=60)
def get_exact_contribution(df_top):
    # Lớp 1: Gọi API của TCBS (Mở hoàn toàn, không chặn Streamlit)
    try:
        url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/intraday/index/ticker-contribute?index=VNINDEX"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'data' in data and len(data['data']) > 0:
                df = pd.DataFrame(data['data'])
                # Chuyển đổi tên cột của TCBS cho khớp với hệ thống của chúng ta
                return df[['ticker', 'point']].rename(columns={'ticker': 'Mã CK', 'point': 'Điểm'})
    except Exception as e:
        pass # Nếu TCBS lỗi, trôi xuống Lớp 2

    # Lớp 2: Dùng vnstock3 (Nguồn phụ)
    try:
        from vnstock3 import Vnstock
        vn = Vnstock()
        df = vn.market_watch.tickers_contrib_index(index='VNINDEX')
        if not df.empty:
            str_cols = [c for c in df.columns if df[c].dtype == 'object']
            num_cols = [c for c in df.columns if df[c].dtype != 'object']
            if str_cols and num_cols:
                return df[[str_cols[0], num_cols[0]]].rename(columns={str_cols[0]: 'Mã CK', num_cols[0]: 'Điểm'})
    except:
        pass

    # Lớp 3: Mô phỏng dựa trên Top 100 (Chống sập giao diện)
    if not df_top.empty:
        df_sim = df_top.copy()
        weights = {'VCB': 4.5, 'BID': 3.0, 'VIC': 2.5, 'VHM': 2.5, 'CTG': 2.0, 'TCB': 2.0, 'FPT': 1.8, 'HPG': 1.5, 'GAS': 1.5}
        df_sim['Weight'] = df_sim['Mã CK'].map(lambda x: weights.get(x, 0.5))
        df_sim['Điểm'] = (df_sim['%'] * df_sim['Weight']) / 3.0
        return df_sim[['Mã CK', 'Điểm']]

    return pd.DataFrame()
