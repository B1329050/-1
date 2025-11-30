import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, div_df, chip_df, margin_df, info):
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.rev = rev_df 
        self.div = div_df
        self.chip = chip_df
        self.margin = margin_df
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
            # 寬容度搜尋 (前後 45 天)
            mask = (df.index >= target_date - pd.Timedelta(days=45)) & \
                   (df.index <= target_date + pd.Timedelta(days=45))
            if any(mask):
                valid_date = df[mask].index[0]
                return self._get_value_smart(df, valid_date, key)
            return None
        except: return None

    # ========================================================
    # 1. 融資籌碼分析 (Margin Analysis)
    # ========================================================
    def calculate_margin_metrics(self):
        try:
            if self.margin.empty: return {}
            df = self.margin.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=True)
            
            # 模糊搜尋欄位
            col_name = None
            possible_cols = ['MarginPurchaseBalance', 'MarginBalance', 'MarginPurchaseTodayBalance']
            for c in df.columns:
                if any(x in c for x in possible_cols): col_name = c; break
            
            if not col_name: return {}

            df_recent = df.tail(20)
            if len(df_recent) < 2: return {}
            
            latest = df_recent.iloc[-1][col_name]
            prev_idx = -6 if len(df_recent) >= 6 else 0
            prev = df_recent.iloc[prev_idx][col_name]
            
            return {
                "Margin Increasing": latest > prev,
                "Latest Balance": latest,
                "Change": (latest - prev)
            }
        except: return {}

    # ========================================================
    # 2. 籌碼分析 (Chip Analysis - 雙語模糊比對)
    # ========================================================
    def calculate_chip_metrics(self):
        try:
            if self.chip.empty: return {}
            df = self.chip.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=True)
            
            if 'name' not in df.columns: return {}
            df['name'] = df['name'].astype(str)

            # 外資 (包含 Foreign 或 外資)
            foreign = df[df['name'].str.contains('Foreign|外資', case=False, regex=True)].tail(3)
            foreign_net = 0; foreign_consecutive = False
            
            if not foreign.empty:
                # 強制轉型防呆
                for c in ['buy', 'sell']:
                    foreign[c] = pd.to_numeric(foreign[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                net = foreign['buy'] - foreign['sell']
                foreign_net = net.sum()
                if len(foreign) >= 3:
                    foreign_consecutive = (net > 0).all()

            # 投信 (包含 Trust 或 投信)
            trust = df[df['name'].str.contains('Trust|投信', case=False, regex=True)].tail(10)
            trust_net = 0
            if not trust.empty:
                for c in ['buy', 'sell']:
                    trust[c] = pd.to_numeric(trust[c].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                trust_net = (trust['buy'] - trust['sell']).sum()
            
            market_cap = self.info.get('marketCap', 0)
            is_small_cap = 0 < market_cap < (50 * 100000000) 
            trust_active = (trust_net > 0) and is_small_cap

            return {
                "Foreign Net (3d)": foreign_net,
                "Foreign Consecutive": foreign_consecutive,
                "Trust Net (10d)": trust_net,
                "Trust Active Buy": trust_active,
                "Is Small Cap": is_small_cap
            }
        except: return {}

    # ========================================================
    # 3. 大師指標 (Guru Metrics) - [TTM 修正版]
    # ========================================================
    def calculate_guru_metrics(self):
        try:
            if self.bs.empty or self.inc.empty: return {}
            curr_date = self.inc.index[0]
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            # --- A. 葛拉漢數 (5年平均 EPS) ---
            equity = get(self.bs, 'EQUITY'); common_stock = get(self.bs, 'COMMON_STOCK')
            shares = (common_stock / 10) if common_stock > 0 else 1
            bvps = equity / shares if shares > 0 else 0

            avg_eps = 0; eps_values = []
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
            ncav = (curr_assets - get(self.bs, 'LIABILITIES')) / shares if shares > 0 else 0

            # --- B. 林區 PEG ---
            _, yoy_rev = self.calculate_revenue_growth()
            growth = yoy_rev if yoy_rev else 0
            mcap = self.info.get('marketCap', 0)
            
            lynch_cat = "未分類"
            if growth > 20: lynch_cat = "🚀 快速成長"
            elif 10 < growth <= 20: lynch_cat = "🛡️ 穩定成長"
            elif growth < 5 and mcap > 500*100000000: lynch_cat = "🐢 緩慢成長"
            elif growth < 0: lynch_cat = "🔄 循環/轉機"

            div_yield = 0
            if not self.div.empty:
                try:
                    last_div = self.div.sort_values('date').iloc[-1]['CashEarningsDistribution']
                    price = self.info.get('currentPrice', 1)
                    if price > 0: div_yield = (last_div / price) * 100
                except: pass
            
            pe = self.info.get('trailingPE', 0)
            lynch_peg = pe / (growth + div_yield) if (growth + div_yield) > 0 and pe > 0 else None

            # --- C. 神奇公式 (TTM 修正版) [cite: 55-60] ---
            # 報告要求: 避免使用單一年度，需平滑波動。
            # 實作: 滾動加總過去 4 季 (TTM) 的 EBIT
            
            ebit_ttm = 0
            count = 0
            # 往前抓 4 季
            for i in range(min(4, len(self.inc))):
                d = self.inc.index[i]
                val = self._get_value_smart(self.inc, d, 'EBIT')
                if val == 0: 
                    val = self._get_value_smart(self.inc, d, 'PRE_TAX_INCOME') + \
                          self._get_value_smart(self.inc, d, 'INTEREST_EXPENSE')
                
                if val != 0:
                    ebit_ttm += val
                    count += 1
            
            # 若資料不足 4 季，則用平均值年化
            if count > 0 and count < 4:
                ebit_ttm = (ebit_ttm / count) * 4
            elif count == 0:
                ebit_ttm = 0

            fixed_assets = get(self.bs, 'FIXED_ASSETS')
            if fixed_assets == 0: fixed_assets = self._get_value_smart(self.bs, curr_date, 'NON_CURRENT_ASSETS')
            
            wc = curr_assets - curr_liab
            ic = fixed_assets + wc
            
            # 使用 TTM EBIT 計算 ROC
            magic_roc = (ebit_ttm / ic * 100) if ic > 0 else 0

            debt = get(self.bs, 'LIABILITIES'); cash = get(self.bs, 'CASH')
            if cash==0: cash = self._get_value_smart(self.bs, curr_date, 'CashAndCashEquivalents')
            ev = mcap + debt - cash
            magic_ey = (ebit_ttm / ev * 100) if ev > 0 else 0

            return {
                "Graham Number": graham_number, "NCAV": ncav,
                "Lynch Category": lynch_cat, "Lynch PEG": lynch_peg,
                "Magic ROC": magic_roc, "Magic EY": magic_ey,
                "Avg EPS": avg_eps, "Current Ratio": current_ratio
            }
        except Exception as e: 
            return {}

    # ========================================================
    # 4. 營收動能 (Revenue Growth)
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
    # 5. F-Score
    # ========================================================
    def calculate_f_score(self):
        score = 0; details = []
        if self.inc.empty or self.bs.empty: return 0, ["❌ 數據缺失"]
        try:
            curr_date = self.inc.index[0]
            def get(df, k): return self._get_value_smart(df, curr_date, k)
            def get_p(df, k): return self._get_prev_value(df, curr_date, k)

            ni = get(self.inc, 'NET_INCOME'); assets = get(self.bs, 'ASSETS'); cfo = get(self.cf, 'OPERATING_CASH_FLOW')
            if assets>0 and ni/assets>0: score+=1; details.append("✅ ROA > 0")
            if cfo>0: score+=1; details.append("✅ CFO > 0")
            if cfo>ni: score+=1; details.append("✅ CFO > NI")
            p_ni = get_p(self.inc, 'NET_INCOME'); p_assets = get_p(self.bs, 'ASSETS')
            if p_ni and p_assets and (ni/assets)>(p_ni/p_assets): score+=1; details.append("✅ ROA YoY > 0")
            
            lev = get(self.bs, 'LIABILITIES') - get(self.bs, 'CURRENT_LIABILITIES')
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

            rev = get(self.inc, 'REVENUE'); cost = get(self.inc, 'OPERATING_COSTS')
            p_rev = get_p(self.inc, 'REVENUE'); p_cost = get_p(self.inc, 'OPERATING_COSTS')
            if rev>0 and cost>0 and p_rev and p_cost:
                if ((rev-cost)/rev) > ((p_rev-p_cost)/p_rev): score+=1; details.append("✅ 毛利率提升")
            if assets>0 and p_assets and (rev/assets)>(p_rev/p_assets): score+=1; details.append("✅ 週轉率提升")
        except Exception as e: details.append(f"計算中斷: {e}")
        return score, details

    # ========================================================
    # 6. Z-Score
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
