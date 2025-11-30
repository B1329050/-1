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
                    return func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        print(f"⚠️ 達到 API 限制，暫停 {delay} 秒後重試...")
                        time.sleep(delay)
                    else:
                        print(f"API Error ({i+1}/{retries}): {e}")
                        return pd.DataFrame()
            return pd.DataFrame()
        return wrapper
    return decorator

# --- 獨立快取函式 ---

@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    """獲取股價與基本資料"""
    yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except Exception as e:
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_fundamentals_data(stock_id, api_token_str):
    """
    [第一路] 抓取基本面 (財報 + 營收 + 股利)
    特性：資料量較小，抓取週期長 (5年)，確保葛拉漢數與營收 YoY 能計算
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # 抓 5 年
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    @rate_limit_handler()
    def safe_fetch(func, **kwargs): return func(**kwargs)

    # 這裡放入所有「非每日更新」或「輕量級」的數據
    tasks = [
        'taiwan_stock_balance_sheet',
        'taiwan_stock_financial_statement',
        'taiwan_stock_cash_flows_statement',
        'taiwan_stock_month_revenue',  # [移回這裡] 營收很重要，確保它跟財報一起成功
        'taiwan_stock_dividend'
    ]
    
    results = []
    for name in tasks:
        if hasattr(fm, name):
            func = getattr(fm, name)
            df = safe_fetch(func, stock_id=stock_id, start_date=start_date)
            results.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame())
        else:
            results.append(pd.DataFrame())
        
        if not api_token_str: time.sleep(1)

    while len(results) < 5: results.append(pd.DataFrame())
    return results # bs, inc, cf, rev, div

@st.cache_data(ttl=21600) # 籌碼盤中/盤後更新，快取設短一點
def fetch_chip_data(stock_id, api_token_str):
    """
    [第二路] 抓取籌碼面 (三大法人 + 融資)
    特性：資料量極大，只抓取「最近 90 天」，避免 API Timeout
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # [關鍵修正] 只抓 90 天 (約 3 個月)，足夠判斷外資連買與投信認養
    # 抓 1 年會導致 FinMind 回傳失敗 (0張的原因)
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    @rate_limit_handler()
    def safe_fetch(func, **kwargs): return func(**kwargs)

    tasks = [
        'taiwan_stock_institutional_investors_buy_sell',
        'taiwan_stock_margin_purchase_short_sale'
    ]
    
    results = []
    for name in tasks:
        # 動態檢查，避免舊版 FinMind 報錯
        if hasattr(fm, name):
            func = getattr(fm, name)
            df = safe_fetch(func, stock_id=stock_id, start_date=start_date)
            results.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame())
        else:
            results.append(pd.DataFrame())
            
        if not api_token_str: time.sleep(1)

    while len(results) < 2: results.append(pd.DataFrame())
    return results # chip, margin

# --- DataEngine 類別 ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        # 1. 啟動基本面引擎 (穩)
        bs, inc, cf, rev, div = fetch_fundamentals_data(stock_id, self.token)
        
        # 2. 啟動籌碼引擎 (快)
        chip, margin = fetch_chip_data(stock_id, self.token)
        
        # 3. 組裝 7 大寶石回傳
        return bs, inc, cf, rev, div, chip, margin
