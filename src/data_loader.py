# src/data_loader.py
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import streamlit as st
from datetime import datetime, timedelta
import time
from .config import DATASETS

class DataEngine:
    def __init__(self, token=None):
        self.fm = DataLoader()
        self.token = token
        if self.token:
            self.fm.login(token=token)
        else:
            print("⚠️ 警告: 未檢測到 FinMind Token。將使用免費限制模式 (可能會遇到請求頻率限制)。")

    @st.cache_data(ttl=3600)
    def get_price_data(self, ticker):
        """
        獲取價格數據 (yfinance)
        """
        # 處理台股代碼後綴
        yf_ticker = ticker if ticker.endswith(('.TW', '.TWO')) else f"{ticker}.TW"
        
        try:
            stock = yf.Ticker(yf_ticker)
            # 獲取 2 年歷史數據
            df = stock.history(period="2y")
            info = stock.info
            return df, info
        except Exception as e:
            st.error(f"yfinance 數據獲取失敗: {e}")
            return pd.DataFrame(), {}

    @st.cache_data(ttl=86400)
    def get_financial_data(self, stock_id):
        """
        獲取基本面數據 (FinMind)
        """
        # 拉取 5 年數據以確保有足夠的歷史資料做 YoY (防止 index error)
        start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
        
        # 定義要拉取的資料集函數
        fetch_funcs = [
            self.fm.taiwan_stock_balance_sheet,
            self.fm.taiwan_stock_financial_statements,
            self.fm.taiwan_stock_cash_flows,
            self.fm.taiwan_stock_month_revenue
        ]
        
        results = []
        for fetch_func in fetch_funcs:
            try:
                # 執行 API 請求
                df = fetch_func(stock_id=stock_id, start_date=start_date)
                results.append(df)
                
                # [重要] 如果沒有 Token，每抓一個表強制休息 3 秒，避免被 Server 封鎖
                if not self.token:
                    time.sleep(3) 
            except Exception as e:
                st.error(f"FinMind 數據拉取失敗: {e}")
                results.append(pd.DataFrame()) # 失敗時塞入空 DataFrame

        # 依序回傳：資產負債表, 損益表, 現金流量表, 月營收
        return results[0], results[1], results[2], results[3]

    def get_realtime_mops_revenue(self, stock_id):
        """
        MOPS 爬蟲預留接口
        目前回傳 None，由 FinMind 數據補位。
        """
        return None
