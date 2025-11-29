# src/data_loader.py
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import functools
from .config import DATASETS

# --- [實作報告 4.1] Python 裝飾器處理速率限制 ---
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
                        print(f"API Error: {e}")
                        # 若非限流錯誤，回傳空 DataFrame 避免崩潰
                        return pd.DataFrame()
            return pd.DataFrame()
        return wrapper
    return decorator

@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5y") # 抓長一點算 CAGR
        info = stock.info
        return df, info
    except Exception as e:
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_financials_from_finmind(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try:
            fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # [報告 2.1.1] 葛拉漢需要 3-5 年數據算平均 EPS，故拉取 5 年
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    # 定義內部函數以套用 Retry
    @rate_limit_handler()
    def safe_fetch(func, **kwargs):
        return func(**kwargs)

    datasets = [
        fm.taiwan_stock_balance_sheet,
        fm.taiwan_stock_financial_statement,
        fm.taiwan_stock_cash_flows_statement,
        fm.taiwan_stock_month_revenue,
        fm.taiwan_stock_dividend # [新增] 股利表
    ]
    
    results = []
    for func in datasets:
        df = safe_fetch(func, stock_id=stock_id, start_date=start_date)
        if isinstance(df, pd.DataFrame):
            results.append(df)
        else:
            results.append(pd.DataFrame())
        
        if not api_token_str: time.sleep(2)

    while len(results) < 5: results.append(pd.DataFrame())
        
    return results[0], results[1], results[2], results[3], results[4]

class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        return fetch_financials_from_finmind(stock_id, self.token)
