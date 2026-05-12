import requests, urllib.parse, pytz
from datetime import datetime, timedelta
import pandas as pd
from vnstock import stock_historical_data

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def get_dates():
    now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    return now.strftime('%Y-%m-%d'), (now - timedelta(days=60)).strftime('%Y-%m-%d')

def fetch_proxy(target_url):
    encoded = urllib.parse.quote(target_url, safe='')
    urls = [target_url, f"https://api.codetabs.com/v1/proxy?quest={encoded}", f"https://api.allorigins.win/raw?url={encoded}"]
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200 and len(res.content) > 50: return res.text
        except: continue
    return None

def get_vnindex_ma():
    end_d, start_ma = get_dates()
    try:
        df = stock_historical_data('VNINDEX', start_ma, end_d, '1D', 'index')
        if not df.empty:
            df['MA20'] = df['close'].rolling(20).mean()
            df['VMA20'] = df['volume'].rolling(20).mean()
            return df.dropna().reset_index(drop=True)
    except: pass
    return pd.DataFrame()
