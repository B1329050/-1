import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
from .config import DATASETS

# --- 簡單粗暴的重試函式 ---
def fetch_with_retry(func, stock_id, start_date, retries=5, delay=2):
    for i in range(retries):
        try:
            df = func(stock_id=stock_id, start_date=start_date)
            # 只有當 df 是 DataFrame 且 不為空 時才算成功
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
            # 如果是空的，休息一下再試 (除非是真的很冷門的股票)
            time.sleep(delay)
        except Exception as e:
            print(f"Fetch Error ({i}): {e}")
            time.sleep(delay)
    return pd.DataFrame() # 盡力了，回傳空表

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
    # 財報抓 5 年
    date_long = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    # 這裡資料量小，重試 3 次即可
    bs = fetch_with_retry(fm.taiwan_stock_balance_sheet, clean_id, date_long, 3)
    inc = fetch_with_retry(fm.taiwan_stock_financial_statement, clean_id, date_long, 3)
    if inc.empty: inc = fetch_with_retry(fm.taiwan_stock_financial_statements, clean_id, date_long, 3)
    
    cf = fetch_with_retry(fm.taiwan_stock_cash_flows_statement, clean_id, date_long, 3)
    # [重要] 營收移到這裡抓，確保有數據
    rev = fetch_with_retry(fm.taiwan_stock_month_revenue, clean_id, date_long, 3)
    div = fetch_with_retry(fm.taiwan_stock_dividend, clean_id, date_long, 3)

    return bs, inc, cf, rev, div

# --- 3. 籌碼面 (三大法人/融資) ---
@st.cache_data(ttl=21600) 
def fetch_chip_data(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    
    # [極限修正] 只抓 30 天，保證資料量極小，秒殺下載
    date_short = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # [暴力重試] 針對籌碼 (institutional) 重試 5 次，每次休息 3 秒
    # 這是最容易失敗的環節，必須加強火力
    if hasattr(fm, 'taiwan_stock_institutional_investors_buy_sell'):
        chip = fetch_with_retry(fm.taiwan_stock_institutional_investors_buy_sell, clean_id, date_short, retries=5, delay=3)
    else:
        chip = pd.DataFrame()

    if hasattr(fm, 'taiwan_stock_margin_purchase_short_sale'):
        margin = fetch_with_retry(fm.taiwan_stock_margin_purchase_short_sale, clean_id, date_short, retries=5, delay=3)
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
