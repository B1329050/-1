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
def fetch_financials_from_finmind(stock_id, api_token_str):
    """
    獲取 7 大報表 (使用動態屬性呼叫，避免 AttributeError)
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try:
            fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    @rate_limit_handler()
    def safe_fetch(func, **kwargs):
        return func(**kwargs)

    # [關鍵修正] 這裡必須有 7 個項目！
    dataset_method_names = [
        'taiwan_stock_balance_sheet',
        'taiwan_stock_financial_statement',
        'taiwan_stock_cash_flows_statement',
        'taiwan_stock_month_revenue',
        'taiwan_stock_dividend',
        'taiwan_stock_institutional_investors_buy_sell',
        'taiwan_stock_margin_purchase_short_sale' # [補回] 融資融券
    ]
    
    results = []
    
    for method_name in dataset_method_names:
        # 動態檢查 DataLoader 是否有這個功能 (防崩潰核心)
        if hasattr(fm, method_name):
            func = getattr(fm, method_name)
            df = safe_fetch(func, stock_id=stock_id, start_date=start_date)
            if isinstance(df, pd.DataFrame):
                results.append(df)
            else:
                results.append(pd.DataFrame())
        else:
            print(f"⚠️ 警告: 當前 FinMind 版本不支援 {method_name}")
            results.append(pd.DataFrame())
        
        if not api_token_str: time.sleep(1.5)

    # 補齊 7 個 DataFrame，避免 unpacking error
    while len(results) < 7: results.append(pd.DataFrame())
        
    return results[0], results[1], results[2], results[3], results[4], results[5], results[6]


# --- DataEngine 類別 ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        return fetch_financials_from_finmind(stock_id, self.token)
