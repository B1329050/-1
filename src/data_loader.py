import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import functools
from .config import DATASETS

# --- API 速率限制裝飾器 ---
def rate_limit_handler(retries=3, delay=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    result = func(*args, **kwargs)
                    if isinstance(result, pd.DataFrame) and not result.empty:
                        return result
                    time.sleep(delay) # 失敗休息
                except Exception as e:
                    time.sleep(delay)
            return pd.DataFrame()
        return wrapper
    return decorator

# --- 獨立快取函式 ---

@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    # Yahoo 需要 .TW
    yf_ticker = ticker.strip()
    if not yf_ticker.endswith(('.TW', '.TWO')): 
        yf_ticker += ".TW"
        
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except:
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_fundamentals_data(stock_id, api_token_str):
    """基本面 (5年)"""
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # [關鍵修正] 淨化 Stock ID，FinMind 不吃 .TW
    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    @rate_limit_handler(retries=3, delay=2)
    def get_df(func_name, **kwargs):
        if hasattr(fm, func_name): return getattr(fm, func_name)(**kwargs)
        return pd.DataFrame()

    bs = get_df('taiwan_stock_balance_sheet', stock_id=clean_id, start_date=start_date)
    inc = get_df('taiwan_stock_financial_statement', stock_id=clean_id, start_date=start_date)
    if inc.empty: inc = get_df('taiwan_stock_financial_statements', stock_id=clean_id, start_date=start_date)
    cf = get_df('taiwan_stock_cash_flows_statement', stock_id=clean_id, start_date=start_date)
    rev = get_df('taiwan_stock_month_revenue', stock_id=clean_id, start_date=start_date)
    div = get_df('taiwan_stock_dividend', stock_id=clean_id, start_date=start_date)

    return bs, inc, cf, rev, div

@st.cache_data(ttl=21600) 
def fetch_chip_data(stock_id, api_token_str):
    """籌碼面 (35天) - 極限瘦身"""
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    start_date = (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d')
    
    @rate_limit_handler(retries=5, delay=3) # 加強重試
    def get_df(func_name, **kwargs):
        if hasattr(fm, func_name): return getattr(fm, func_name)(**kwargs)
        return pd.DataFrame()

    chip = get_df('taiwan_stock_institutional_investors_buy_sell', stock_id=clean_id, start_date=start_date)
    margin = get_df('taiwan_stock_margin_purchase_short_sale', stock_id=clean_id, start_date=start_date)

    return chip, margin

class DataEngine:
    def __init__(self, token=None):
        self.token = token
    def get_price_data(self, ticker): return fetch_price_from_yahoo(ticker)
    def get_financial_data(self, stock_id):
        bs, inc, cf, rev, div = fetch_fundamentals_data(stock_id, self.token)
        chip, margin = fetch_chip_data(stock_id, self.token)
        return bs, inc, cf, rev, div, chip, margin
