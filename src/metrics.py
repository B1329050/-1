import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, div_df, info):
        # 初始化接收所有報表，包含新增的股利表 (div_df)
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
            if target_date in df.index:
                return self._get_value_smart(df, target_date, key)
            return None
        except: return None

    # --- [新功能] 實作研究報告第二章的大師指標 ---
    def calculate_guru_metrics(self):
        """
        計算: 葛拉漢數、林區 PEG、神奇公式 ROC
        """
        try:
            if self.bs.empty or self.inc.empty: return {}
            curr_date = self.inc.index[0]
            
            # Helper
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            # 1. 葛拉漢數 (Graham Number) = Sqrt(22.5 * EPS * BVPS)
            equity = get(self.bs, 'EQUITY')
            common_stock = get(self.bs, 'COMMON_STOCK')
            # 估算流通股數 (假設面額10元)，若無股本數據則防呆設為1
            shares = (common_stock / 10) if common_stock > 0 else 1
            bvps = equity / shares if shares > 0 else 0
            
            # 簡化：使用當期 EPS (研究報告建議平均 EPS，但需更多歷史數據，此為 v1 實作)
            current_eps = get(self.inc, 'EPS')
            if current_eps == 0 and shares > 0:
                current_eps = get(self.inc, 'NET_INCOME') / shares

            graham_number = 0
            if current_eps > 0 and bvps > 0:
                graham_number = (22.5 * current_eps * bvps) ** 0.5

            # 2. 林區 PEG (Yield-Adjusted PEG) = PE / (Growth + Dividend Yield)
            # 取得股息殖利率
            div_yield = 0
            if not self.div.empty:
                # 假設最新一筆是最近發放的現金股利
                # FinMind 股利表欄位: date, stock_id, CashEarningsDistribution...
                try:
                    # 確保按日期排序
                    sorted_div = self.div.sort_values('date', ascending=True)
                    last_div = sorted_div.iloc[-1]['CashEarningsDistribution']
                    price = self.info.get('currentPrice', self.info.get('regularMarketPreviousClose', 0))
                    if price > 0:
                        div_yield = (last_div / price) * 100
                except:
                    div_yield = 0
            
            # 取得成長率 (使用營收 YoY)
            _, yoy_rev = self.calculate_revenue_growth()
            growth_rate = yoy_rev if yoy_rev else 0
            
            pe = self.info.get('trailingPE', 0)
            lynch_peg = None
            
            # 避免分母為 0 或負數 (林區 PEG 僅適用於成長股)
            denominator = growth_rate + div_yield
            if denominator > 0 and pe > 0:
                lynch_peg = pe / denominator

            # 3. 神奇公式 ROC = EBIT / (Fixed Assets + Working Capital)
            ebit = get(self.inc, 'EBIT')
            if ebit == 0: 
                ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            fixed_assets = get(self.bs, 'FIXED_ASSETS')
            curr_assets = get(self.bs, 'CURRENT_ASSETS')
            curr_liab = get(self.bs, 'CURRENT_LIABILITIES')
            working_capital = curr_assets - curr_liab
            
            roc = 0
            invested_capital = fixed_assets + working_capital
            if invested_capital > 0:
                roc = (ebit / invested_capital) * 100

            return {
                "Graham Number": graham_number,
                "BVPS": bvps,
                "Lynch PEG": lynch_peg,
                "Div Yield": div_yield,
                "Magic ROC": roc
            }
        except Exception as e:
            # print(f"Guru Metrics Error: {e}") # Debug用
            return {}

    def calculate_revenue_growth(self):
        """
        計算月營收動能 (MoM, YoY)
        """
        try:
            if self.rev.empty: return None, None
            
            df = self.rev.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=False)
            
            val_col = 'revenue'
            # 處理 FinMind 可能的欄位名稱變異
            if val_col not in df.columns:
                if 'value' in df.columns: val_col = 'value'
                else: return None, None 

            if len(df) < 1: return None, None

            # 最新月份
            curr_rev = df.iloc[0][val_col]
            curr_date = df.iloc[0]['date']
            
            # 1. MoM (月增率)
            last_month_rev = df.iloc[1][val_col] if len(df) > 1 else 0
            mom = ((curr_rev - last_month_rev) / last_month_rev * 100) if last_month_rev else 0
            
            # 2. YoY (年增率)
            target_date = curr_date - pd.DateOffset(years=1)
            # 尋找日期最接近的一筆 (前後5天)
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

    # --- 完整的 F-Score 邏輯 (包含容錯機制) ---
    def calculate_f_score(self):
        score = 0
        details = []
        
        if self.inc.empty or self.bs.empty:
            return 0, ["❌ 數據嚴重缺失"]

        try:
            curr_date = self.inc.index[0]
            
            # Helper Functions
            def get(df, key): return self._get_value_smart(df, curr_date, key)
            def get_p(df, key): return self._get_prev_value(df, curr_date, key)
            
            # --- 1. 獲利能力 ---
            ni = get(self.inc, 'NET_INCOME')
            assets = get(self.bs, 'ASSETS')
            cfo = get(self.cf, 'OPERATING_CASH_FLOW')
            
            # ROA > 0
            if assets > 0 and (ni/assets) > 0: 
                score+=1; details.append("✅ ROA > 0")
            
            # CFO > 0
            if cfo > 0: 
                score+=1; details.append("✅ CFO > 0")
            
            # Accruals (CFO > NI)
            if cfo > ni: 
                score+=1; details.append("✅ CFO > NI (盈餘品質佳)")
            
            # ROA YoY
            p_ni = get_p(self.inc, 'NET_INCOME')
            p_assets = get_p(self.bs, 'ASSETS')
            if p_ni is not None and p_assets is not None and p_assets > 0:
                if (ni/assets) > (p_ni/p_assets): 
                    score+=1; details.append("✅ ROA 優於去年")

            # --- 2. 財務結構 ---
            # 長期負債比率下降
            tot_liab = get(self.bs, 'LIABILITIES')
            cur_liab = get(self.bs, 'CURRENT_LIABILITIES')
            lt_debt = tot_liab - cur_liab
            
            p_tot_liab = get_p(self.bs, 'LIABILITIES')
            p_cur_liab = get_p(self.bs, 'CURRENT_LIABILITIES')
            
            if p_tot_liab is not None and p_cur_liab is not None:
                p_lt_debt = p_tot_liab - p_cur_liab
                # 需比較佔資產比率
                if p_assets > 0 and assets > 0:
                    if (lt_debt/assets) <= (p_lt_debt/p_assets): 
                        score+=1; details.append("✅ 長期負債比率下降")

            # 流動比率提升
            cur_assets = get(self.bs, 'CURRENT_ASSETS')
            p_cur_assets = get_p(self.bs, 'CURRENT_ASSETS')
            
            if cur_liab > 0 and p_cur_liab is not None and p_cur_liab > 0 and p_cur_assets is not None:
                if (cur_assets/cur_liab) > (p_cur_assets/p_cur_liab):
                    score+=1; details.append("✅ 流動比率提升")
            
            # 未增資 (股本)
            stock = get(self.bs, 'COMMON_STOCK')
            p_stock = get_p(self.bs, 'COMMON_STOCK')
            if p_stock is not None:
                if stock <= p_stock * 1.05: # 容許 5% 變動 (如盈餘轉增資)
                    score+=1; details.append("✅ 無顯著現金增資")
            else:
                score+=1; details.append("⚠️ 無股本數據，預設通過")

            # --- 3. 營運效率 ---
            # 毛利率提升
            rev = get(self.inc, 'REVENUE')
            cost = get(self.inc, 'OPERATING_COSTS')
            p_rev = get_p(self.inc, 'REVENUE')
            p_cost = get_p(self.inc, 'OPERATING_COSTS')
            
            # 若無成本數據 (如金融業) 則此項可能不適用，這裡採嚴格制 (有資料且提升才給分)
            has_gm = (rev > 0 and cost > 0 and p_rev is not None and p_rev > 0 and p_cost is not None)
            if has_gm:
                gm = (rev - cost) / rev
                p_gm = (p_rev - p_cost) / p_rev
                if gm > p_gm: 
                    score+=1; details.append("✅ 毛利率提升")

            # 資產週轉率提升
            if assets > 0 and p_assets is not None and p_assets > 0 and p_rev is not None:
                if (rev/assets) > (p_rev/p_assets): 
                    score+=1; details.append("✅ 資產週轉率提升")

        except Exception as e:
            details.append(f"⚠️ 計算中斷: {str(e)}")
            
        return score, details

    # --- 完整的 Z-Score 邏輯 ---
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
