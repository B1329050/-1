# src/metrics.py
import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, info):
        # 數據預處理
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.info = info
        
    def _pivot_data(self, df):
        if df.empty: return pd.DataFrame()
        # 轉換為 pivot table
        pivoted = df.pivot_table(index='date', columns='type', values='value')
        # 強制轉換 index 為 datetime 格式，並排序
        pivoted.index = pd.to_datetime(pivoted.index)
        return pivoted.sort_index(ascending=False)

    def _get_prev_value(self, df, curr_date, column):
        """
        嚴謹的 YoY 數據獲取
        """
        try:
            target_date = curr_date - pd.DateOffset(years=1)
            if target_date in df.index:
                return df.loc[target_date, column]
            return None
        except KeyError:
            return None

    def calculate_f_score(self):
        """
        Piotroski F-Score 計算
        """
        score = 0
        details = []
        
        try:
            if self.inc.empty or self.bs.empty or self.cf.empty:
                return 0, ["❌ 數據嚴重缺失，無法計算"]

            curr_date = self.inc.index[0]
            
            # --- 1. 獲利能力 ---
            # ROA > 0
            # 容錯處理：若找不到 NET_INCOME 嘗試用其他欄位，這裡假設 mapping 正確
            net_income = self.inc.loc[curr_date, MAPPING['NET_INCOME']]
            total_assets = self.bs.loc[curr_date, MAPPING['ASSETS']]
            roa = net_income / total_assets
            
            if roa > 0: 
                score += 1
                details.append("✅ ROA 為正")
            
            # CFO > 0
            if MAPPING['OPERATING_CASH_FLOW'] in self.cf.columns:
                cfo = self.cf.loc[curr_date, MAPPING['OPERATING_CASH_FLOW']]
            else:
                cfo = 0 # 若無現金流數據，視為 0
                
            if cfo > 0: 
                score += 1
                details.append("✅ 營運現金流為正")
            
            # ROA 變動
            prev_net_income = self._get_prev_value(self.inc, curr_date, MAPPING['NET_INCOME'])
            prev_total_assets = self._get_prev_value(self.bs, curr_date, MAPPING['ASSETS'])
            
            if prev_net_income is not None and prev_total_assets is not None:
                prev_roa = prev_net_income / prev_total_assets
                if roa > prev_roa: 
                    score += 1
                    details.append("✅ ROA 優於去年")
            
            # 應計項目
            if cfo > net_income: 
                score += 1
                details.append("✅ 現金流大於淨利")

            # --- 2. 財務槓桿與流動性 (修正重點) ---
            
            # [修正] 長期負債比率下降
            # 不直接抓 NonCurrentLiabilities，改用 (總負債 - 流動負債) 計算，避免 KeyError
            
            # 取得當期數據
            curr_total_liab = self.bs.loc[curr_date, MAPPING['LIABILITIES']]
            curr_current_liab = self.bs.loc[curr_date, MAPPING['CURRENT_LIABILITIES']]
            curr_long_term_liab = curr_total_liab - curr_current_liab
            
            # 取得去年數據
            prev_total_liab = self._get_prev_value(self.bs, curr_date, MAPPING['LIABILITIES'])
            prev_current_liab = self._get_prev_value(self.bs, curr_date, MAPPING['CURRENT_LIABILITIES'])
            
            if prev_total_liab is not None and prev_current_liab is not None:
                prev_long_term_liab = prev_total_liab - prev_current_liab
                
                # 計算比率 (長期負債 / 總資產)
                curr_lev = curr_long_term_liab / total_assets
                prev_lev = prev_long_term_liab / prev_total_assets
                
                if curr_lev <= prev_lev: 
                    score += 1
                    details.append("✅ 長期負債比率下降")
            
            # 流動比率上升
            curr_ratio = self.bs.loc[curr_date, MAPPING['CURRENT_ASSETS']] / curr_current_liab
            prev_curr_assets = self._get_prev_value(self.bs, curr_date, MAPPING['CURRENT_ASSETS'])
            
            if prev_curr_assets is not None and prev_current_liab is not None:
                prev_ratio = prev_curr_assets / prev_current_liab
                if curr_ratio > prev_ratio: 
                    score += 1
                    details.append("✅ 流動比率提升")
            
            # 未增資
            curr_share = self.bs.loc[curr_date, 'CommonStock'] if 'CommonStock' in self.bs.columns else 0
            prev_share = self._get_prev_value(self.bs, curr_date, 'CommonStock')
            if prev_share is not None:
                if curr_share <= prev_share * 1.05:
                    score += 1
                    details.append("✅ 無顯著現金增資")
            else:
                score += 1
                details.append("⚠️ 無股本數據，預設通過")

            # --- 3. 營運效率 ---
            # 毛利率提升
            curr_rev = self.inc.loc[curr_date, MAPPING['REVENUE']]
            prev_rev = self._get_prev_value(self.inc, curr_date, MAPPING['REVENUE'])
            curr_cost = self.inc.loc[curr_date, 'OperatingCosts']
            prev_cost = self._get_prev_value(self.inc, curr_date, 'OperatingCosts')
            
            if prev_rev is not None and prev_cost is not None and curr_rev > 0 and prev_rev > 0:
                curr_gm = (curr_rev - curr_cost) / curr_rev
                prev_gm = (prev_rev - prev_cost) / prev_rev
                if curr_gm > prev_gm:
                    score += 1
                    details.append("✅ 毛利率提升")
            
            # 資產週轉率提升
            if prev_rev is not None and prev_total_assets is not None:
                curr_at = curr_rev / total_assets
                prev_at = prev_rev / prev_total_assets
                if curr_at > prev_at:
                    score += 1
                    details.append("✅ 資產週轉率提升")
                
        except Exception as e:
            details.append(f"⚠️ 計算中斷: {str(e)} (可能某個會計科目缺失)")
            
        return score, details

    def calculate_z_score(self):
        """
        Altman Z-Score 計算
        """
        try:
            if self.bs.empty or self.inc.empty:
                return None, "數據缺失"

            # 產業濾網
            sector = self.info.get('sector', '')
            if 'Financial' in sector or 'Bank' in sector or 'Insurance' in sector:
                return None, "⚠️ 金融業不適用"

            date = self.bs.index[0]
            
            # 準備變數
            total_assets = self.bs.loc[date, MAPPING['ASSETS']]
            curr_assets = self.bs.loc[date, MAPPING['CURRENT_ASSETS']]
            curr_liab = self.bs.loc[date, MAPPING['CURRENT_LIABILITIES']]
            total_liab = self.bs.loc[date, MAPPING['LIABILITIES']]
            revenue = self.inc.loc[date, MAPPING['REVENUE']]
            
            # X2: 保留盈餘 (容錯處理)
            retained_earnings = 0
            if MAPPING['RETAINED_EARNINGS'] in self.bs.columns:
                retained_earnings = self.bs.loc[date, MAPPING['RETAINED_EARNINGS']]
            elif 'UnappropriatedRetainedEarnings' in self.bs.columns: # FinMind 另一種常見命名
                 retained_earnings = self.bs.loc[date, 'UnappropriatedRetainedEarnings']

            # X3: EBIT
            if 'EBIT' in self.inc.columns:
                ebit = self.inc.loc[date, 'EBIT']
            else:
                pre_tax = self.inc.loc[date, MAPPING['PRE_TAX_INCOME']]
                interest = self.inc.loc[date, MAPPING['INTEREST_EXPENSE']] if MAPPING['INTEREST_EXPENSE'] in self.inc.columns else 0
                ebit = pre_tax + interest
            
            market_cap = self.info.get('marketCap', 0)
            
            # 計算五大比率
            x1 = (curr_assets - curr_liab) / total_assets
            x2 = retained_earnings / total_assets
            x3 = ebit / total_assets
            x4 = market_cap / total_liab
            x5 = revenue / total_assets
            
            z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
            return z_score, "計算完成"
            
        except Exception as e:
            return None, f"計算失敗: {str(e)}"
