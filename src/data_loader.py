import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import functools
from .config import DATASETS

# --- [實作] API 速率限制裝飾器 (Rate Limit Decorator) ---
# 參考報告章節 4.1 "Python 裝飾器處理速率限制" 
def rate_limit_handler(retries=3, delay=5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 捕捉 429 Too Many Requests
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        print(f"⚠️ 達到 API 限制，暫停 {delay} 秒後重試...")
                        time.sleep(delay)
                    else:
                        print(f"API Error ({i+1}/{retries}): {e}")
                        # 若非限流錯誤，回傳空 DataFrame 避免崩潰
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
        # 抓 5 年是為了計算長期的 Beta 或波動率，雖此版未用但保留彈性
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except Exception as e:
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_financials_from_finmind(stock_id, api_token_str):
    """
    獲取六大報表：資產負債、損益、現金流、營收、股利、籌碼
    """
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try:
            fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    # 抓取 5 年數據以計算長期平均 (如葛拉漢數)
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    # 套用裝飾器以保護 API 請求
    @rate_limit_handler()
    def safe_fetch(func, **kwargs):
        return func(**kwargs)

    # 定義抓取清單 (注意函式名稱單複數)
    datasets_funcs = [
        fm.taiwan_stock_balance_sheet,
        fm.taiwan_stock_financial_statement,      # 單數
        fm.taiwan_stock_cash_flows_statement,     # 複數+statement
        fm.taiwan_stock_month_revenue,
        fm.taiwan_stock_dividend,
        fm.taiwan_stock_institutional_investors_buy_sell # [新增] 三大法人
    ]
    
    results = []
    for func in datasets_funcs:
        df = safe_fetch(func, stock_id=stock_id, start_date=start_date)
        if isinstance(df, pd.DataFrame):
            results.append(df)
        else:
            results.append(pd.DataFrame())
        
        # 免費模式強制休息
        if not api_token_str: time.sleep(1.5)

    # 補齊 6 個 DataFrame
    while len(results) < 6: results.append(pd.DataFrame())
        
    return results[0], results[1], results[2], results[3], results[4], results[5]


# --- DataEngine 類別 (介面層) ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        return fetch_financials_from_finmind(stock_id, self.token)
