import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, div_df, chip_df, info):
        # 初始化接收所有報表 (含 chip_df)
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.rev = rev_df 
        self.div = div_df
        self.chip = chip_df # [重要] 籌碼資料
        self.info = info
        
    def _pivot_data(self, df):
        if df.empty: return pd.DataFrame()
        try:
            pivoted = df.pivot_table(index='date', columns='type', values='value')
            pivoted.index = pd.to_datetime(pivoted.index)
            return pivoted.sort_index(ascending=False)
        except: return pd.DataFrame()

    def _get_value_smart(self, df, date, key):
        """智慧查找：根據 Config 中的同義詞列表尋找欄位"""
        possible_names = MAPPING.get(key, [])
        if not possible_names: possible_names = [key]
        for name in possible_names:
            if name in df.columns:
                val = df.loc[date, name]
                if pd.notna(val): return val
        return 0

    def _get_prev_value(self, df, curr_date, key):
        """取得去年同期數據 (YoY)"""
        try:
            target_date = curr_date - pd.DateOffset(years=1)
            mask = (df.index >= target_date - pd.Timedelta(days=45)) & \
                   (df.index <= target_date + pd.Timedelta(days=45))
            if any(mask):
                valid_date = df[mask].index[0]
                return self._get_value_smart(df, valid_date, key)
            return None
        except: return None

    # ========================================================
    # 1. 在地化籌碼分析 (Chip Analysis) [之前遺漏的部分]
    # ========================================================
    def calculate_chip_metrics(self):
        """
        計算三大法人動向：外資連買、投信認養
        """
        try:
            if self.chip.empty: return {}
            
            # 整理數據 (三大法人表是 Long Format)
            df = self.chip.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=True) # 按時間排序
            
            # 取最近 60 天數據 (足夠判斷趨勢)
            # 每天有 3 筆資料 (外資, 投信, 自營)，所以取 180 筆
            df_recent = df.tail(180) 
            
            # A. 外資連續買超 (Foreign Trend)
            # 篩選外資 (Foreign_Investor)
            foreign = df_recent[df_recent['name'] == 'Foreign_Investor'].tail(3)
            foreign_consecutive_buy = False
            if len(foreign) >= 3:
                # 檢查最後 3 筆是否買大於賣
                foreign_consecutive_buy = (foreign['buy'] > foreign['sell']).all()

            # B. 投信作帳 (Investment Trust Alpha)
            # 條件: 投信近期(10日)淨買超 > 0 且 為中小型股
            trust = df_recent[df_recent['name'] == 'Investment_Trust'].tail(10)
            trust_net_buy = (trust['buy'] - trust['sell']).sum()
            
            market_cap = self.info.get('marketCap', 0)
            # 50億台幣約 1.6 億美金
            is_small_cap = market_cap < (50 * 100000000) 
            
            trust_active = (trust_net_buy > 0) and is_small_cap

            return {
                "Foreign Consecutive Buy": foreign_consecutive_buy,
                "Trust Active Buy": trust_active,
                "Trust Net Buy": trust_net_buy
            }
        except Exception as e:
            # print(f"Chip Error: {e}")
            return {}

    # ========================================================
    # 2. 大師指標 (Guru Metrics)
    # ========================================================
    def calculate_guru_metrics(self):
        try:
            if self.bs.empty or self.inc.empty: return {}
            curr_date = self.inc.index[0]
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            # --- 葛拉漢數 (5年平均 EPS) ---
            equity = get(self.bs, 'EQUITY')
            common_stock = get(self.bs, 'COMMON_STOCK')
            shares = (common_stock / 10) if common_stock > 0 else 1
            bvps = equity / shares if shares > 0 else 0

            avg_eps = 0
            eps_values = []
            for i in range(min(20, len(self.inc))):
                d = self.inc.index[i]
                q_eps = self._get_value_smart(self.inc, d, 'EPS')
                if q_eps == 0 and shares > 0:
                    ni = self._get_value_smart(self.inc, d, 'NET_INCOME')
                    q_eps = ni / shares
                if q_eps != 0: eps_values.append(q_eps)
            
            if eps_values: avg_eps = (sum(eps_values) / len(eps_values)) * 4
            graham_number = (22.5 * avg_eps * bvps) ** 0.5 if (avg_eps > 0 and bvps > 0) else 0

            curr_assets = get(self.bs, 'CURRENT_ASSETS')
            curr_liab = get(self.bs, 'CURRENT_LIABILITIES')
            current_ratio = (curr_assets / curr_liab) if curr_liab > 0 else 0
            
            # --- 林區 PEG (殖利率修正) ---
            div_yield = 0
            if not self.div.empty:
                try:
                    last_div = self.div.sort_values('date').iloc[-1]['CashEarningsDistribution']
                    price = self.info.get('currentPrice', self.info.get('regularMarketPreviousClose', 0))
                    if price > 0: div_yield = (last_div / price) * 100
                except: pass
            
            _, yoy_rev = self.calculate_revenue_growth()
            growth = yoy_rev if yoy_rev else 0
            pe = self.info.get('trailingPE', 0)
            lynch_peg = pe / (growth + div_yield) if (growth + div_yield) > 0 and pe > 0 else None

            # --- 神奇公式 (ROC + EY) ---
            ebit = get(self.inc, 'EBIT')
            if ebit == 0: ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            fixed_assets = get(self.bs, 'FIXED_ASSETS')
            if fixed_assets == 0: fixed_assets = self._get_value_smart(self.bs, curr_date, 'NON_CURRENT_ASSETS')
            
            wc = curr_assets - curr_liab
            ic = fixed_assets + wc
            magic_roc = (ebit / ic * 100) if ic > 0 else 0

            mcap = self.info.get('marketCap', 0)
            debt = get(self.bs, 'LIABILITIES')
            cash = get(self.bs, 'CASH')
            ev = mcap + debt - cash
            magic_ey = (ebit / ev * 100) if ev > 0 else 0

            return {
                "Graham Number": graham_number, "Avg EPS": avg_eps,
                "Current Ratio": current_ratio, "Lynch PEG": lynch_peg,
                "Magic ROC": magic_roc, "Magic EY": magic_ey
            }
        except: return {}

    # ========================================================
    # 3. 營收動能 (Revenue Growth)
    # ========================================================
    def calculate_revenue_growth(self):
        try:
            if self.rev.empty: return None, None
            df = self.rev.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=False)
            val_col = 'revenue'
            if val_col not in df.columns:
                if 'value' in df.columns: val_col = 'value'
                else: return None, None 
            if len(df) < 2: return None, None
            curr_rev = df.iloc[0][val_col]
            last_month_rev = df.iloc[1][val_col]
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

    # ========================================================
    # 4. F-Score (完整版)
    # ========================================================
    def calculate_f_score(self):
        score = 0; details = []
        if self.inc.empty or self.bs.empty: return 0, ["❌ 數據缺失"]
        try:
            curr_date = self.inc.index[0]
            def get(df, k): return self._get_value_smart(df, curr_date, k)
            def get_p(df, k): return self._get_prev_value(df, curr_date, k)

            # 獲利
            ni = get(self.inc, 'NET_INCOME'); assets = get(self.bs, 'ASSETS')
            cfo = get(self.cf, 'OPERATING_CASH_FLOW')
            if assets>0 and ni/assets>0: score+=1; details.append("✅ ROA > 0")
            if cfo>0: score+=1; details.append("✅ CFO > 0")
            if cfo>ni: score+=1; details.append("✅ CFO > NI (盈餘品質)")
            
            # 趨勢
            p_ni = get_p(self.inc, 'NET_INCOME'); p_assets = get_p(self.bs, 'ASSETS')
            if p_ni and p_assets and (ni/assets)>(p_ni/p_assets): score+=1; details.append("✅ ROA YoY > 0")

            # 結構
            lev = (get(self.bs, 'LIABILITIES') - get(self.bs, 'CURRENT_LIABILITIES'))
            p_lev = get_p(self.bs, 'LIABILITIES')
            if p_lev: 
                p_lev_val = p_lev - get_p(self.bs, 'CURRENT_LIABILITIES')
                if assets>0 and p_assets>0 and (lev/assets)<=(p_lev_val/p_assets): score+=1; details.append("✅ 負債比下降")
            
            cur = get(self.bs, 'CURRENT_ASSETS'); cur_l = get(self.bs, 'CURRENT_LIABILITIES')
            p_cur = get_p(self.bs, 'CURRENT_ASSETS'); p_cur_l = get_p(self.bs, 'CURRENT_LIABILITIES')
            if cur_l>0 and p_cur_l and (cur/cur_l)>(p_cur/p_cur_l): score+=1; details.append("✅ 流動比上升")
            
            stk = get(self.bs, 'COMMON_STOCK'); p_stk = get_p(self.bs, 'COMMON_STOCK')
            if p_stk and stk<=p_stk*1.05: score+=1; details.append("✅ 無顯著增資")
            elif not p_stk: score+=1; details.append("⚠️ 無股本數據通過")

            # 效率
            rev = get(self.inc, 'REVENUE'); cost = get(self.inc, 'OPERATING_COSTS')
            p_rev = get_p(self.inc, 'REVENUE'); p_cost = get_p(self.inc, 'OPERATING_COSTS')
            if rev>0 and cost>0 and p_rev and p_cost:
                if ((rev-cost)/rev) > ((p_rev-p_cost)/p_rev): score+=1; details.append("✅ 毛利率提升")
            
            if assets>0 and p_assets and (rev/assets)>(p_rev/p_assets): score+=1; details.append("✅ 週轉率提升")

        except Exception as e: details.append(f"計算中斷: {e}")
        return score, details

    # ========================================================
    # 5. Z-Score (完整版)
    # ========================================================
    def calculate_z_score(self):
        try:
            if self.bs.empty: return None, "無數據"
            if any(x in self.info.get('sector','') for x in ['Financial', 'Bank', 'Insurance']): return None, "金融業不適用"
            
            curr_date = self.bs.index[0]
            def get(df, k): return self._get_value_smart(df, curr_date, k)
            
            ta = get(self.bs, 'ASSETS'); tl = get(self.bs, 'LIABILITIES')
            if ta==0 or tl==0: return None, "資產/負債為0"

            x1 = (get(self.bs, 'CURRENT_ASSETS') - get(self.bs, 'CURRENT_LIABILITIES')) / ta
            x2 = get(self.bs, 'RETAINED_EARNINGS') / ta
            
            ebit = get(self.inc, 'EBIT')
            if ebit==0: ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            x3 = ebit / ta
            
            x4 = self.info.get('marketCap', 0) / tl
            x5 = get(self.inc, 'REVENUE') / ta
            
            z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
            return z, "計算完成"
        except Exception as e: return None, str(e)
