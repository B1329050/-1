import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, div_df, info):
        # 初始化接收所有報表
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.rev = rev_df 
        self.div = div_df
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
            # 寬容度搜尋 (前後 30 天) 避免日期沒對齊
            mask = (df.index >= target_date - pd.Timedelta(days=30)) & \
                   (df.index <= target_date + pd.Timedelta(days=30))
            if any(mask):
                valid_date = df[mask].index[0]
                return self._get_value_smart(df, valid_date, key)
            return None
        except: return None

    # ========================================================
    # 1. 大師指標 (Guru Metrics) - 依照研究報告實作
    # ========================================================
    def calculate_guru_metrics(self):
        try:
            if self.bs.empty or self.inc.empty: return {}
            curr_date = self.inc.index[0]
            
            # Helper
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            # --- A. 葛拉漢數 (Graham Number) ---
            # 公式: Sqrt(22.5 * Avg_EPS * BVPS)
            # 報告要求: 使用 3-5 年平均 EPS
            
            equity = get(self.bs, 'EQUITY')
            common_stock = get(self.bs, 'COMMON_STOCK')
            shares = (common_stock / 10) if common_stock > 0 else 1
            bvps = equity / shares if shares > 0 else 0

            # 計算 5 年平均 EPS
            avg_eps = 0
            eps_values = []
            
            # 遍歷最多 20 季 (5年)
            for i in range(min(20, len(self.inc))):
                d = self.inc.index[i]
                quarter_eps = self._get_value_smart(self.inc, d, 'EPS')
                if quarter_eps == 0 and shares > 0:
                    ni = self._get_value_smart(self.inc, d, 'NET_INCOME')
                    quarter_eps = ni / shares
                
                if quarter_eps != 0:
                    eps_values.append(quarter_eps)
            
            if eps_values:
                # 將季平均轉為年化
                avg_eps = (sum(eps_values) / len(eps_values)) * 4
            else:
                avg_eps = 0

            graham_number = 0
            if avg_eps > 0 and bvps > 0:
                graham_number = (22.5 * avg_eps * bvps) ** 0.5

            # 葛拉漢防禦型檢查
            curr_assets = get(self.bs, 'CURRENT_ASSETS')
            curr_liab = get(self.bs, 'CURRENT_LIABILITIES')
            current_ratio = (curr_assets / curr_liab) if curr_liab > 0 else 0
            
            working_capital = curr_assets - curr_liab
            long_term_debt = get(self.bs, 'NON_CURRENT_LIABILITIES')
            debt_guard = (long_term_debt < working_capital)

            # --- B. 林區 PEG (Yield-Adjusted) ---
            # 公式: PE / (Growth + Dividend Yield)
            
            div_yield = 0
            if not self.div.empty:
                try:
                    sorted_div = self.div.sort_values('date', ascending=True)
                    last_div = sorted_div.iloc[-1]['CashEarningsDistribution']
                    price = self.info.get('currentPrice', self.info.get('regularMarketPreviousClose', 0))
                    if price > 0:
                        div_yield = (last_div / price) * 100
                except: pass
            
            _, yoy_rev = self.calculate_revenue_growth()
            growth_rate = yoy_rev if yoy_rev else 0
            
            pe = self.info.get('trailingPE', 0)
            lynch_peg = None
            if (growth_rate + div_yield) > 0 and pe > 0:
                lynch_peg = pe / (growth_rate + div_yield)

            # --- C. 神奇公式 (Magic Formula) ---
            # 1. 資本報酬率 ROC = EBIT / (Fixed Assets + Working Capital)
            ebit = get(self.inc, 'EBIT')
            if ebit == 0: 
                ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            fixed_assets = get(self.bs, 'FIXED_ASSETS')
            # 若無固定資產欄位，嘗試用非流動資產替代
            if fixed_assets == 0: fixed_assets = self._get_value_smart(self.bs, curr_date, 'NON_CURRENT_ASSETS')
            
            invested_capital = fixed_assets + working_capital
            magic_roc = (ebit / invested_capital * 100) if invested_capital > 0 else 0

            # 2. 盈餘殖利率 Earnings Yield = EBIT / Enterprise Value
            market_cap = self.info.get('marketCap', 0)
            total_debt = get(self.bs, 'LIABILITIES')
            cash = get(self.bs, 'CASH')
            if cash == 0: cash = self._get_value_smart(self.bs, curr_date, 'CashAndCashEquivalents')
            
            enterprise_value = market_cap + total_debt - cash
            magic_ey = (ebit / enterprise_value * 100) if enterprise_value > 0 else 0

            return {
                "Graham Number": graham_number,
                "Avg EPS (5yr)": avg_eps,
                "Current Ratio": current_ratio,
                "Debt Guard": debt_guard,
                "Lynch PEG": lynch_peg,
                "Magic ROC": magic_roc,
                "Magic EY": magic_ey
            }
        except Exception as e:
            # print(f"Guru Metrics Error: {e}")
            return {}

    # ========================================================
    # 2. 營收動能 (Revenue Growth)
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
        except:
            return None, None

    # ========================================================
    # 3. F-Score (皮爾托斯基) - 完整實作
    # ========================================================
    def calculate_f_score(self):
        score = 0
        details = []
        
        if self.inc.empty or self.bs.empty:
            return 0, ["❌ 數據嚴重缺失"]

        try:
            curr_date = self.inc.index[0]
            
            # Helper
            def get(df, key): return self._get_value_smart(df, curr_date, key)
            def get_p(df, key): return self._get_prev_value(df, curr_date, key)
            
            # --- A. 獲利能力 ---
            ni = get(self.inc, 'NET_INCOME')
            assets = get(self.bs, 'ASSETS')
            cfo = get(self.cf, 'OPERATING_CASH_FLOW')
            
            if assets > 0 and (ni/assets) > 0: 
                score+=1; details.append("✅ ROA > 0")
            
            if cfo > 0: 
                score+=1; details.append("✅ CFO > 0")
            
            if cfo > ni: 
                score+=1; details.append("✅ CFO > NI (盈餘品質佳)")
            
            p_ni = get_p(self.inc, 'NET_INCOME')
            p_assets = get_p(self.bs, 'ASSETS')
            if p_ni is not None and p_assets is not None and p_assets > 0:
                if (ni/assets) > (p_ni/p_assets): 
                    score+=1; details.append("✅ ROA 優於去年")

            # --- B. 財務結構 ---
            tot_liab = get(self.bs, 'LIABILITIES')
            cur_liab = get(self.bs, 'CURRENT_LIABILITIES')
            lt_debt = tot_liab - cur_liab
            
            p_tot_liab = get_p(self.bs, 'LIABILITIES')
            p_cur_liab = get_p(self.bs, 'CURRENT_LIABILITIES')
            
            if p_tot_liab is not None and p_cur_liab is not None:
                p_lt_debt = p_tot_liab - p_cur_liab
                if p_assets is not None and p_assets > 0 and assets > 0:
                    if (lt_debt/assets) <= (p_lt_debt/p_assets): 
                        score+=1; details.append("✅ 長期負債比率下降")

            cur_assets = get(self.bs, 'CURRENT_ASSETS')
            p_cur_assets = get_p(self.bs, 'CURRENT_ASSETS')
            
            if cur_liab > 0 and p_cur_liab is not None and p_cur_liab > 0 and p_cur_assets is not None:
                if (cur_assets/cur_liab) > (p_cur_assets/p_cur_liab):
                    score+=1; details.append("✅ 流動比率提升")
            
            stock = get(self.bs, 'COMMON_STOCK')
            p_stock = get_p(self.bs, 'COMMON_STOCK')
            if p_stock is not None:
                if stock <= p_stock * 1.05: 
                    score+=1; details.append("✅ 無顯著現金增資")
            else:
                score+=1; details.append("⚠️ 無股本數據，預設通過")

            # --- C. 營運效率 ---
            rev = get(self.inc, 'REVENUE')
            cost = get(self.inc, 'OPERATING_COSTS')
            p_rev = get_p(self.inc, 'REVENUE')
            p_cost = get_p(self.inc, 'OPERATING_COSTS')
            
            # 毛利率檢查
            has_gm = (rev > 0 and cost > 0 and p_rev is not None and p_rev > 0 and p_cost is not None)
            if has_gm:
                gm = (rev - cost) / rev
                p_gm = (p_rev - p_cost) / p_rev
                if gm > p_gm: 
                    score+=1; details.append("✅ 毛利率提升")

            # 資產週轉率檢查
            if assets > 0 and p_assets is not None and p_assets > 0 and p_rev is not None:
                if (rev/assets) > (p_rev/p_assets): 
                    score+=1; details.append("✅ 資產週轉率提升")

        except Exception as e:
            details.append(f"⚠️ 計算中斷: {str(e)}")
            
        return score, details

    # ========================================================
    # 4. Z-Score (奧特曼) - 完整實作
    # ========================================================
    def calculate_z_score(self):
        try:
            if self.bs.empty: return None, "無數據"
            
            # 產業濾網
            sector = self.info.get('sector', '')
            if 'Financial' in sector or 'Bank' in sector or 'Insurance' in sector:
                return None, "金融業不適用"

            curr_date = self.bs.index[0]
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            ta = get(self.bs, 'ASSETS')
            tl = get(self.bs, 'LIABILITIES')
            ca = get(self.bs, 'CURRENT_ASSETS')
            cl = get(self.bs, 'CURRENT_LIABILITIES')
            
            re = get(self.bs, 'RETAINED_EARNINGS')
            rev = get(self.inc, 'REVENUE')
            
            # EBIT 估算
            ebit = get(self.inc, 'EBIT')
            if ebit == 0:
                ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            mc = self.info.get('marketCap', 0)
            
            if ta == 0 or tl == 0: return None, "資產或負債為0"
            
            x1 = (ca - cl) / ta
            x2 = re / ta
            x3 = ebit / ta
            x4 = mc / tl
            x5 = rev / ta
            
            z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
            return z, "計算完成"
            
        except Exception as e:
            return None, f"計算失敗: {str(e)}"
