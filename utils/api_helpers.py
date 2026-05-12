import streamlit as st
import pandas as pd
from vnstock import stock_historical_data, listing_companies
from datetime import datetime, timedelta
import pytz
import concurrent.futures
import requests
import urllib.parse
import re

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')

def get_dates():
    now = datetime.now(vn_tz)
    return now.strftime('%Y-%m-%d'), (now - timedelta(days=7)).strftime('%Y-%m-%d'), (now - timedelta(days=60)).strftime('%Y-%m-%d')

def fetch_proxy(target_url, is_json=True):
    encoded = urllib.parse.quote(target_url, safe='')
    urls = [target_url, f"https://api.codetabs.com/v1/proxy?quest={encoded}", f"https://api.allorigins.win/raw?url={encoded}"]
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200 and len(res.content) > 50:
                return res.json() if is_json else res.text
        except: continue
    return None

@st.cache_data(ttl=86400)
def get_sectors():
    try:
        df = listing_companies()
        return df[(df['comGroupCode'] == 'HOSE') & (df['ticker'].str.len() == 3)][['ticker', 'sector']].set_index('ticker').to_dict()['sector']
    except: return {}

@st.cache_data(ttl=120)
def get_top_100():
    sectors = get_sectors()
    d_end, d_7, _ = get_dates()
    def fetch_t(ticker):
        try:
            df = stock_historical_data(ticker, d_7, d_end, '1D', 'stock')
            if len(df) >= 2:
                c, p = df.iloc[-1]['close'], df.iloc[-2]['close']
                return {'Mã CK': ticker, 'Nhóm Ngành': sectors.get(ticker, 'Khác'), 'Giá': c, '+/-': round(c-p, 2), '%': round((c-p)/p*100, 2), 'Tổng KL': int(df.iloc[-1]['volume'])}
        except: return None
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        for res in exe.map(fetch_t, list(sectors.keys())):
            if res and res['Tổng KL'] > 0: results.append(res)
    df = pd.DataFrame(results)
    return df.sort_values('Tổng KL', ascending=False).head(100) if not df.empty else pd.DataFrame()

@st.cache_data(ttl=60)
def get_idx_live():
    d_end, d_7, _ = get_dates()
    return stock_historical_data('VNINDEX', d_7, d_end, '1', 'index')

@st.cache_data(ttl=60)
def get_index_contrib():
    data = fetch_proxy("https://finfo-api.vndirect.com.vn/v4/index_events?q=code:VNINDEX&sort=point~DESC&size=30", True)
    if data and 'data' in data:
        df = pd.DataFrame(data['data'])[['ticker', 'point']]
        df.columns = ['Mã CK', 'Điểm']
        df['Điểm'] = pd.to_numeric(df['Điểm'])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vnindex_ma():
    d_end, _, d_60 = get_dates()
    try:
        df = stock_historical_data('VNINDEX', d_60, d_end, '1D', 'index')
        if not df.empty:
            df['MA20'], df['VMA20'] = df['close'].rolling(20).mean(), df['volume'].rolling(20).mean()
            return df.dropna().reset_index(drop=True)
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_cafef_reports():
    html = fetch_proxy("https://s.cafef.vn/ajax/KhuyenNghi_Update.aspx?PageIndex=1&PageSize=30", False)
    res = []
    if html:
        for b in re.findall(r'<li.*?>(.*?)</li>', html, re.DOTALL):
            t_m, l_m = re.search(r'class="doc_title"[^>]*>(.*?)</a>', b), re.search(r'href="(/Report/Download\.aspx\?id=[^"]+)"', b)
            if t_m and l_m:
                t = t_m.group(1).strip()
                tk = (re.search(r'\b([A-Z0-9]{3})\b', t) or re.search('','')).group(0)
                act, t_up = "ĐÁNH GIÁ", t.upper()
                if any(w in t_up for w in ["MUA", "MỤC TIÊU", "KHẢ QUAN", "ADD"]): act = "MUA / KHẢ QUAN"
                elif any(w in t_up for w in ["BÁN", "SELL"]): act = "BÁN"
                elif any(w in t_up for w in ["NẮM GIỮ", "HOLD"]): act = "NẮM GIỮ"
                res.append({"Mã CK": tk, "Khuyến nghị": act, "Nội dung": t, "Link": "https://s.cafef.vn" + l_m.group(1)})
    return pd.DataFrame(res)
