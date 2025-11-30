import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import functools
from .config import DATASETS

# --- API 速率限制裝飾器 ---
def rate_limit_handler(retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    result = func(*args, **kwargs)
                    # 確保回傳的是 DataFrame 且不是空的 (FinMind有時回傳空DF代表失敗)
                    if isinstance(result, pd.DataFrame) and not result.empty:
                        return result
                    # 若是空 dataframe，視為失敗，等待重試 (除非真的沒資料)
                    if i < retries - 1:
                        time.sleep(delay)
                        continue
                    return pd.DataFrame()
                except Exception as e:
                    print(f"API Attempt {i+1} Failed: {e}")
                    if i < retries - 1:
                        time.sleep(delay)
                    else:
                        return pd.DataFrame()
            return pd.DataFrame()
        return wrapper
    return decorator

# --- 獨立快取函式 ---

@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except:
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_fundamentals_data(stock_id, api_token_str):
    """
    [第一路] 基本面 (財報/營收/股利)
    週期：5年 (為了葛拉漢數)
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    @rate_limit_handler(retries=3, delay=2)
    def get_df(func_name, **kwargs):
        if hasattr(fm, func_name):
            return getattr(fm, func_name)(**kwargs)
        return pd.DataFrame()

    # 1. 資產負債表
    bs = get_df('taiwan_stock_balance_sheet', stock_id=stock_id, start_date=start_date)
    # 2. 損益表 (嘗試單複數命名)
    inc = get_df('taiwan_stock_financial_statement', stock_id=stock_id, start_date=start_date)
    if inc.empty: inc = get_df('taiwan_stock_financial_statements', stock_id=stock_id, start_date=start_date)
    # 3. 現金流量表
    cf = get_df('taiwan_stock_cash_flows_statement', stock_id=stock_id, start_date=start_date)
    # 4. 月營收 (很重要，移來這裡抓)
    rev = get_df('taiwan_stock_month_revenue', stock_id=stock_id, start_date=start_date)
    # 5. 股利
    div = get_df('taiwan_stock_dividend', stock_id=stock_id, start_date=start_date)

    return bs, inc, cf, rev, div

@st.cache_data(ttl=21600) 
def fetch_chip_data(stock_id, api_token_str):
    """
    [第二路] 籌碼面 (法人/融資)
    週期：【關鍵修正】只抓 30 天！保證資料量極小，絕對成功。
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # 極限瘦身：只看過去 1 個月 (足夠判斷連買與趨勢)
    start_date = (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d')
    
    @rate_limit_handler(retries=5, delay=2) # 增加重試次數
    def get_df(func_name, **kwargs):
        if hasattr(fm, func_name):
            return getattr(fm, func_name)(**kwargs)
        return pd.DataFrame()

    # 1. 三大法人
    chip = get_df('taiwan_stock_institutional_investors_buy_sell', stock_id=stock_id, start_date=start_date)
    
    # 2. 融資融券
    margin = get_df('taiwan_stock_margin_purchase_short_sale', stock_id=stock_id, start_date=start_date)

    return chip, margin

# --- DataEngine 類別 ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        # 1. 基本面 (5年)
        bs, inc, cf, rev, div = fetch_fundamentals_data(stock_id, self.token)
        # 2. 籌碼面 (30天)
        chip, margin = fetch_chip_data(stock_id, self.token)
        
        # 強制休息避免短時間請求過多 (針對免費用戶)
        if not self.token: time.sleep(1)
        
        return bs, inc, cf, rev, div, chip, margin
