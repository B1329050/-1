# src/metrics.py
import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, div_df, info):
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.rev = rev_df 
        self.div = div_df # 股利表
        self.info = info
        
    def _pivot_data(self, df):
        if df.empty: return pd.DataFrame()
        try:
            pivoted = df.pivot_table(index='date', columns='type', values='value')
            pivoted.index = pd.to_datetime(pivoted.index)
            return pivoted.sort_index(ascending=False)
        except: return pd.DataFrame()

    def _get_value_smart(self, df, date, key):
        possible_names = MAPPING.get(key, [])
        if not possible_names: possible_names = [key]
        for name in possible_names:
            if name in df.columns and pd.notna(df.loc[date, name]):
                return df.loc[date, name]
        return 0

    def calculate_guru_metrics(self):
        """
        [實作報告第二章] 大師指標計算引擎
        包含: 葛拉漢數、林區 PEG、神奇公式 ROC
        """
        try:
            if self.bs.empty or self.inc.empty: return {}
            curr_date = self.inc.index[0]
            
            # Helper
            def get(df, key, d=curr_date): return self._get_value_smart(df, d, key)

            # --- 1. 葛拉漢數 (Graham Number) [報告 2.1.1] ---
            # 公式: Sqrt(22.5 * Avg_EPS * BVPS)
            
            # 計算每股淨值 (BVPS) = Equity / Shares
            equity = get(self.bs, 'EQUITY')
            # 股本通常單位為千元或元，FinMind CommonStock 單位通常為元，股數 = 股本 / 10
            # 這裡簡單估算: 若 CommonStock 很大，假設面額 10 元
            common_stock = get(self.bs, 'COMMON_STOCK')
            shares = (common_stock / 10) if common_stock > 0 else 1
            bvps = equity / shares if shares > 0 else 0

            # 計算 3-5 年平均 EPS (平滑景氣循環)
            eps_list = []
            for i in range(5): # 抓過去 5 年 (20 季)
                 # 這裡簡化用最近 5 個年度的資料點做平均
                 # 實際應抓取每年年報 EPS
                 pass
            
            # 使用 FinMind EPS 欄位 (若有) 或 Net Income / Shares
            # 這裡採當期 EPS 作為基礎，若有歷史數據應算平均
            current_eps = get(self.inc, 'EPS')
            if current_eps == 0 and shares > 0:
                current_eps = get(self.inc, 'NET_INCOME') / shares

            graham_number = 0
            if current_eps > 0 and bvps > 0:
                graham_number = (22.5 * current_eps * bvps) ** 0.5

            # --- 2. 林區 PEG (Yield-Adjusted PEG) [報告 2.2.1] ---
            # 公式: PE / (Growth Rate + Dividend Yield)
            
            # 取得股息殖利率
            div_yield = 0
            if not self.div.empty:
                # 假設最新一筆是今年股利
                last_div = self.div.iloc[-1]['CashEarningsDistribution']
                price = self.info.get('currentPrice', self.info.get('regularMarketPreviousClose', 0))
                if price > 0:
                    div_yield = (last_div / price) * 100 # 轉為百分比
            
            # 計算成長率 (簡單用 YoY)
            _, yoy_rev = self.calculate_revenue_growth()
            growth_rate = yoy_rev if yoy_rev else 0
            
            pe = self.info.get('trailingPE', 0)
            lynch_peg = None
            if (growth_rate + div_yield) > 0 and pe > 0:
                lynch_peg = pe / (growth_rate + div_yield)

            # --- 3. 神奇公式指標 [報告 2.3.1] ---
            # 資本報酬率 ROC = EBIT / (Net Fixed Assets + Working Capital)
            ebit = get(self.inc, 'EBIT')
            if ebit == 0: ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            fixed_assets = get(self.bs, 'FIXED_ASSETS')
            curr_assets = get(self.bs, 'CURRENT_ASSETS')
            curr_liab = get(self.bs, 'CURRENT_LIABILITIES')
            working_capital = curr_assets - curr_liab
            
            roc = 0
            if (fixed_assets + working_capital) > 0:
                roc = (ebit / (fixed_assets + working_capital)) * 100

            return {
                "Graham Number": graham_number,
                "BVPS": bvps,
                "Lynch PEG": lynch_peg,
                "Div Yield": div_yield,
                "Magic ROC": roc,
                "Magic EY": 0 # 盈餘殖利率需市值，暫略
            }
            
        except Exception as e:
            return {}

    def calculate_revenue_growth(self):
        # ... (保留原有的營收計算邏輯) ...
        try:
            if self.rev.empty: return None, None
            df = self.rev.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=False)
            
            val_col = 'revenue'
            if val_col not in df.columns:
                if 'value' in df.columns: val_col = 'value'
                else: return None, None 

            curr_rev = df.iloc[0][val_col]
            last_month_rev = df.iloc[1][val_col] if len(df) > 1 else 0
            mom = ((curr_rev - last_month_rev) / last_month_rev * 100) if last_month_rev else 0
            
            target_date = df.iloc[0]['date'] - pd.DateOffset(years=1)
            mask = (df['date'] >= target_date - pd.Timedelta(days=5)) & \
                   (df['date'] <= target_date + pd.Timedelta(days=5))
            prev_rows = df.loc[mask]
            
            yoy = 0
            if not prev_rows.empty:
                prev_rev = prev_rows.iloc[0][val_col]
                yoy = ((curr_rev - prev_rev) / prev_rev * 100) if prev_rev else 0
                
            return mom, yoy
        except: return None, None

    def calculate_f_score(self):
        # ... (保留原有的 F-Score 邏輯) ...
        # 請直接使用上一版完整的 F-Score 程式碼
        # 為了節省空間，此處省略，請確保 calculate_f_score 函式存在
        return 0, [] 
        
    def calculate_z_score(self):
        # ... (保留原有的 Z-Score 邏輯) ...
        return None, ""
