import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
from .config import DATASETS

# --- 智慧階梯式重試 (關鍵修正) ---
def fetch_smart_retry(func, stock_id, retries=3):
    """
    策略：資料量太大會失敗，所以如果失敗了，就縮短天數再試一次。
    30天 -> 10天 -> 5天 -> 3天
    """
    # 定義嘗試的天數級距
    days_options = [30, 10, 5, 3]
    
    for days in days_options:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        # 每個天數嘗試 retries 次
        for i in range(retries):
            try:
                df = func(stock_id=stock_id, start_date=start_date)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df # 成功抓到！
                time.sleep(1) # 休息一下
            except Exception:
                time.sleep(1)
        # 如果這個天數失敗了，迴圈會進入下一個更短的天數 (e.g., 30 -> 10)
        print(f"⚠️ 抓取 {days} 天資料失敗，嘗試縮短天數...")
    
    return pd.DataFrame() # 徹底失敗

# --- 1. 股價與基本資料 ---
@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
    clean_id = ticker.replace('.TW', '').replace('.TWO', '').strip() + ".TW"
    try:
        stock = yf.Ticker(clean_id)
        df = stock.history(period="5y")
        info = stock.info
        return df, info
    except:
        return pd.DataFrame(), {}

# --- 2. 基本面 (財報/營收) ---
@st.cache_data(ttl=86400)
def fetch_fundamentals_data(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    date_long = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    def get(func):
        try:
            df = func(stock_id=clean_id, start_date=date_long)
            return df if not df.empty else pd.DataFrame()
        except: return pd.DataFrame()

    bs = get(fm.taiwan_stock_balance_sheet)
    inc = get(fm.taiwan_stock_financial_statement)
    if inc.empty: inc = get(fm.taiwan_stock_financial_statements)
    
    cf = get(fm.taiwan_stock_cash_flows_statement)
    rev = get(fm.taiwan_stock_month_revenue)
    div = get(fm.taiwan_stock_dividend)

    return bs, inc, cf, rev, div

# --- 3. 籌碼面 (三大法人/融資) ---
@st.cache_data(ttl=21600) 
def fetch_chip_data(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    
    # [修正] 使用階梯式降級抓取
    if hasattr(fm, 'taiwan_stock_institutional_investors_buy_sell'):
        chip = fetch_smart_retry(fm.taiwan_stock_institutional_investors_buy_sell, clean_id)
    else:
        chip = pd.DataFrame()

    # 融資通常資料量小，直接抓 30 天即可，若失敗再降級
    if hasattr(fm, 'taiwan_stock_margin_purchase_short_sale'):
        margin = fetch_smart_retry(fm.taiwan_stock_margin_purchase_short_sale, clean_id)
    else:
        margin = pd.DataFrame()

    return chip, margin

class DataEngine:
    def __init__(self, token=None):
        self.token = token
    def get_price_data(self, ticker): return fetch_price_from_yahoo(ticker)
    def get_financial_data(self, stock_id):
        bs, inc, cf, rev, div = fetch_fundamentals_data(stock_id, self.token)
        chip, margin = fetch_chip_data(stock_id, self.token)
        return bs, inc, cf, rev, div, chip, margin
