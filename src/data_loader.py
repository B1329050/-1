import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import functools
from .config import DATASETS

# --- API 速率限制裝飾器 ---
def rate_limit_handler(retries=3, delay=5):
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

# --- 獨立快取函式 1: 股價 ---
@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except Exception as e:
        return pd.DataFrame(), {}

# --- 獨立快取函式 2: 財報 (冷數據 - 季/年更新) ---
# 特性：資料量小，但需要長週期 (5年) 來算葛拉漢平均 EPS
@st.cache_data(ttl=86400) # 24小時更新一次即可
def fetch_long_term_fundamentals(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # 抓 5 年
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    @rate_limit_handler()
    def safe_fetch(func, **kwargs): return func(**kwargs)

    # 定義: 資產負債、損益、現金流、股利
    tasks = [
        ('taiwan_stock_balance_sheet', fm.taiwan_stock_balance_sheet),
        ('taiwan_stock_financial_statement', fm.taiwan_stock_financial_statement),
        ('taiwan_stock_cash_flows_statement', fm.taiwan_stock_cash_flows_statement),
        ('taiwan_stock_dividend', fm.taiwan_stock_dividend)
    ]
    
    results = []
    for name, func in tasks:
        # 動態檢查確保 FinMind 版本支援
        if hasattr(fm, name) or func: 
            # 兼容性處理：有些版本 func 是 None
            real_func = getattr(fm, name) if hasattr(fm, name) else func
            df = safe_fetch(real_func, stock_id=stock_id, start_date=start_date)
            results.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame())
        else:
            results.append(pd.DataFrame())
        
        if not api_token_str: time.sleep(1)

    while len(results) < 4: results.append(pd.DataFrame())
    return results # bs, inc, cf, div

# --- 獨立快取函式 3: 籌碼與營收 (熱數據 - 日/月更新) ---
# 特性：資料量巨大 (每日一筆)，只抓 1 年以避免 API Timeout
@st.cache_data(ttl=21600) # 6小時更新一次 (盤中/盤後)
def fetch_short_term_chips(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # 只抓 1 年 (關鍵差異！)
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    @rate_limit_handler()
    def safe_fetch(func, **kwargs): return func(**kwargs)

    # 定義: 營收、三大法人、融資
    tasks = [
        ('taiwan_stock_month_revenue', fm.taiwan_stock_month_revenue),
        ('taiwan_stock_institutional_investors_buy_sell', getattr(fm, 'taiwan_stock_institutional_investors_buy_sell', None)),
        ('taiwan_stock_margin_purchase_short_sale', getattr(fm, 'taiwan_stock_margin_purchase_short_sale', None))
    ]
    
    results = []
    for name, func in tasks:
        # 動態屬性檢查 (針對籌碼函式可能不存在的情況)
        real_func = getattr(fm, name) if hasattr(fm, name) else func
        
        if real_func:
            df = safe_fetch(real_func, stock_id=stock_id, start_date=start_date)
            results.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame())
        else:
            print(f"⚠️ 警告: 無法執行 {name}")
            results.append(pd.DataFrame())
            
        if not api_token_str: time.sleep(1)

    while len(results) < 3: results.append(pd.DataFrame())
    return results # rev, chip, margin

# --- DataEngine 類別 (組裝工廠) ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        # 1. 啟動冷數據引擎 (5年財報)
        bs, inc, cf, div = fetch_long_term_fundamentals(stock_id, self.token)
        
        # 2. 啟動熱數據引擎 (1年籌碼)
        rev, chip, margin = fetch_short_term_chips(stock_id, self.token)
        
        # 3. 組裝並回傳 7 個結果，保持 main.py 不用改
        return bs, inc, cf, rev, div, chip, margin
