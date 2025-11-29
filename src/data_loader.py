# src/data_loader.py
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
from .config import DATASETS

# --- 獨立的快取函式 (放在 Class 外面以避免 Hash 錯誤) ---

@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    """
    獨立獲取價格函式 (Yahoo Finance)
    """
    # 處理台股代碼後綴
    yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
    try:
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="2y")
        info = stock.info
        return df, info
    except Exception as e:
        print(f"Yahoo Finance Error: {e}")
        return pd.DataFrame(), {}

@st.cache_data(ttl=86400)
def fetch_financials_from_finmind(stock_id, api_token_str):
    """
    獨立獲取財報函式 (FinMind)
    """
    fm = DataLoader()
    
    # 處理登入邏輯
    if api_token_str and str(api_token_str).strip():
        try:
            fm.login_by_token(api_token=str(api_token_str).strip())
        except Exception:
            pass # 登入失敗就用免費模式

    # 拉取 5 年數據
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    results = []
    
    # 這裡修正了函式名稱 (注意 financial_statement 沒有 s)
    datasets = [
        fm.taiwan_stock_balance_sheet,
        fm.taiwan_stock_financial_statement,  # <--- 修正點：原本多了一個 s
        fm.taiwan_stock_cash_flows,
        fm.taiwan_stock_month_revenue
    ]
    
    for func in datasets:
        try:
            df = func(stock_id=stock_id, start_date=start_date)
            if isinstance(df, pd.DataFrame):
                results.append(df)
            else:
                results.append(pd.DataFrame())
            
            # 免費模式休息機制
            if not api_token_str:
                time.sleep(2)
        except Exception as e:
            print(f"FinMind Fetch Error: {e}")
            results.append(pd.DataFrame())

    # 補齊 4 個 DataFrame
    while len(results) < 4:
        results.append(pd.DataFrame())
        
    return results[0], results[1], results[2], results[3]


# --- DataEngine 類別 ---

class DataEngine:
    def __init__(self, token=None):
        self.token = token

    def get_price_data(self, ticker):
        return fetch_price_from_yahoo(ticker)

    def get_financial_data(self, stock_id):
        return fetch_financials_from_finmind(stock_id, self.token)

    def get_realtime_mops_revenue(self, stock_id):
        return None
