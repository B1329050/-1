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
        # 初始化 DataLoader
        self.fm = DataLoader()
        self.token = token
        
        # --- 穩健的登入邏輯 ---
        # 只有當 Token 有值且不為空字串時才嘗試登入
        if self.token and str(self.token).strip():
            try:
                # 嘗試使用 Token 登入
                self.fm.login_by_token(api_token=str(self.token).strip())
                # 這裡不顯示成功訊息以免干擾介面，失敗才會警告
            except Exception as e:
                # 登入失敗時，捕捉錯誤但不讓程式當機
                print(f"FinMind 登入失敗 (將降級為免費模式): {e}")
                self.token = None # 強制切換回免費模式
        else:
            # 如果使用者沒輸入，就確保 token 是 None
            self.token = None

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
            # 捕捉錯誤並回傳空值，避免當機
            print(f"yfinance Error: {e}")
            return pd.DataFrame(), {}

    @st.cache_data(ttl=86400)
    def get_financial_data(self, stock_id):
        """
        獲取基本面數據 (FinMind)
        """
        # 拉取 5 年數據
        start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
        
        # 定義要拉取的資料集
        fetch_funcs = [
            self.fm.taiwan_stock_balance_sheet,
            self.fm.taiwan_stock_financial_statements,
            self.fm.taiwan_stock_cash_flows,
            self.fm.taiwan_stock_month_revenue
        ]
        
        results = []
        
        # 逐一拉取報表
        for func in fetch_funcs:
            try:
                # 執行 API 請求
                df = func(stock_id=stock_id, start_date=start_date)
                
                # 檢查回傳的是不是 DataFrame (有時候 FinMind 會回傳錯誤訊息字典)
                if isinstance(df, pd.DataFrame):
                    results.append(df)
                else:
                    results.append(pd.DataFrame()) # 格式不對就塞空表
                
                # [保護機制] 如果是免費模式，強制休息，避免被封鎖
                if not self.token:
                    time.sleep(2) 
                    
            except Exception as e:
                # 捕捉單一報表拉取失敗，塞入空表，讓其他報表繼續跑
                print(f"FinMind 拉取單項失敗: {e}")
                results.append(pd.DataFrame())

        # 確保回傳四個 DataFrame (即使是空的)
        while len(results) < 4:
            results.append(pd.DataFrame())

        return results[0], results[1], results[2], results[3]

    def get_realtime_mops_revenue(self, stock_id):
        return None
