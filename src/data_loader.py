import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
import requests # 直接用 requests

# --- 1. [核心修正] 繞過 SDK，直接打 API ---
def fetch_raw_api(dataset, stock_id, start_date, token=None):
    """
    暴力直連 FinMind 伺服器，不透過套件包裝。
    """
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
        "token": token if token else ""
    }
    
    # 重試機制 (3次)
    for i in range(3):
        try:
            r = requests.get(url, params=params, timeout=10) # 設定超時
            if r.status_code == 200:
                data = r.json()
                if data.get('msg') == 'success' and data.get('data'):
                    df = pd.DataFrame(data['data'])
                    return df
            time.sleep(1)
        except Exception as e:
            print(f"Raw Fetch Error ({dataset}): {e}")
            time.sleep(1)
    
    return pd.DataFrame()

# --- 2. 股價 (Yahoo) ---
@st.cache_data(ttl=3600)
def fetch_price_from_yahoo(ticker):
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

# --- 3. 基本面 (財報/營收) - 維持 SDK (因為這部分沒壞) ---
@st.cache_data(ttl=86400)
def fetch_fundamentals_data(stock_id, api_token_str):
    fm = DataLoader()
    if api_token_str and str(api_token_str).strip():
        try: fm.login_by_token(api_token=str(api_token_str).strip())
        except: pass

    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    
    def get_df(func):
        try:
            df = func(stock_id=clean_id, start_date=start_date)
            return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
        except: return pd.DataFrame()

    bs = get_df(fm.taiwan_stock_balance_sheet)
    inc = get_df(fm.taiwan_stock_financial_statement)
    if inc.empty: inc = get_df(fm.taiwan_stock_financial_statements)
    cf = get_df(fm.taiwan_stock_cash_flows_statement)
    rev = get_df(fm.taiwan_stock_month_revenue)
    div = get_df(fm.taiwan_stock_dividend)

    return bs, inc, cf, rev, div

# --- 4. 籌碼面 (三大法人/融資) - 改用直連 ---
@st.cache_data(ttl=21600) 
def fetch_chip_data(stock_id, api_token_str):
    clean_id = stock_id.replace('.TW', '').replace('.TWO', '').strip()
    
    # 只抓 30 天，確保輕量
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # A. 抓籌碼 (直連)
    chip = fetch_raw_api(
        dataset="TaiwanStockInstitutionalInvestorsBuySell",
        stock_id=clean_id,
        start_date=start_date,
        token=api_token_str
    )
    
    # B. 抓融資 (直連)
    margin = fetch_raw_api(
        dataset="TaiwanStockMarginPurchaseShortSale",
        stock_id=clean_id,
        start_date=start_date,
        token=api_token_str
    )

    return chip, margin

# --- DataEngine 類別 ---
class DataEngine:
    def __init__(self, token=None):
        self.token = token
    def get_price_data(self, ticker): return fetch_price_from_yahoo(ticker)
    def get_financial_data(self, stock_id):
        bs, inc, cf, rev, div = fetch_fundamentals_data(stock_id, self.token)
        chip, margin = fetch_chip_data(stock_id, self.token)
        return bs, inc, cf, rev, div, chip, margin
