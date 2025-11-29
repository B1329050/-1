# src/metrics.py
import pandas as pd
import numpy as np
from .config import MAPPING, EXCLUDED_SECTORS

class MetricCalculator:
    def __init__(self, bs_df, inc_df, cf_df, rev_df, info):
        self.bs = self._pivot_data(bs_df)
        self.inc = self._pivot_data(inc_df)
        self.cf = self._pivot_data(cf_df)
        self.rev = rev_df 
        self.info = info
        
    def _pivot_data(self, df):
        if df.empty: return pd.DataFrame()
        # FinMind 財報標準格式: type (科目), value (數值)
        # 若資料不是標準格式 (如月營收)，pivot 可能會失敗，需在外面處理
        try:
            pivoted = df.pivot_table(index='date', columns='type', values='value')
            pivoted.index = pd.to_datetime(pivoted.index)
            return pivoted.sort_index(ascending=False)
        except:
            return pd.DataFrame()

    def _get_prev_value(self, df, curr_date, col_key):
        """
        取得去年同期數據 (YoY)
        col_key: MAPPING 中的鍵 (例如 'REVENUE')
        """
        try:
            target_date = curr_date - pd.DateOffset(years=1)
            # 容許日期有小幅誤差 (財報公告日可能差幾天)
            # 但 FinMind date 通常是季底日 (3/31, 6/30...) 應該精準
            
            # 使用 smart get 找去年數據
            if target_date in df.index:
                return self._get_value_smart(df, target_date, col_key)
            return None
        except:
            return None

    def _get_value_smart(self, df, date, key):
        """
        [核心修復] 智慧欄位查找
        根據 Config 中的清單，依序嘗試所有可能的欄位名稱
        """
        possible_names = MAPPING.get(key, [])
        # 如果 key 本身不在 Mapping 裡，就當作是直接欄位名
        if not possible_names: possible_names = [key]
        
        for name in possible_names:
            if name in df.columns:
                val = df.loc[date, name]
                # 確保不是 NaN
                if pd.notna(val):
                    return val
        return 0 # 找不到回傳 0，避免報錯

    def calculate_revenue_growth(self):
        """
        [修復] 計算月營收動能 (針對 TaiwanStockMonthRevenue 結構)
        """
        try:
            if self.rev.empty: return None, None
            
            # 月營收通常不是 pivot 格式，而是 flat table
            # 欄位通常是: date, revenue, revenue_month, revenue_year ...
            df = self.rev.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=False)
            
            # 確保有 'revenue' 欄位
            val_col = 'revenue'
            if val_col not in df.columns:
                if 'value' in df.columns: val_col = 'value'
                else: return None, None # 找不到營收欄位

            # 最新月份
            curr_rev = df.iloc[0][val_col]
            curr_date = df.iloc[0]['date']
            
            # 1. MoM (月增率)
            last_month_rev = df.iloc[1][val_col] if len(df) > 1 else 0
            mom = ((curr_rev - last_month_rev) / last_month_rev * 100) if last_month_rev else 0
            
            # 2. YoY (年增率)
            # 找去年同月 (往前推 12 筆資料大約就是去年，或是用日期對齊)
            target_date = curr_date - pd.DateOffset(years=1)
            # 尋找日期最接近的一筆
            mask = (df['date'] >= target_date - pd.Timedelta(days=5)) & \
                   (df['date'] <= target_date + pd.Timedelta(days=5))
            prev_rows = df.loc[mask]
            
            yoy = 0
            if not prev_rows.empty:
                prev_rev = prev_rows.iloc[0][val_col]
                yoy = ((curr_rev - prev_rev) / prev_rev * 100) if prev_rev else 0
                
            return mom, yoy
        except Exception as e:
            return None, None

    def calculate_f_score(self):
        score = 0
        details = []
        
        if self.inc.empty or self.bs.empty:
            return 0, ["❌ 數據缺失"]

        try:
            curr_date = self.inc.index[0]
            
            # 簡化寫法，利用 _get_value_smart
            def get(df, key): return self._get_value_smart(df, curr_date, key)
            def get_p(df, key): return self._get_prev_value(df, curr_date, key)

            # 1. 獲利能力
            ni = get(self.inc, 'NET_INCOME')
            assets = get(self.bs, 'ASSETS')
            cfo = get(self.cf, 'OPERATING_CASH_FLOW')
            
            if assets and (ni/assets) > 0: score+=1; details.append("✅ ROA > 0")
            if cfo > 0: score+=1; details.append("✅ CFO > 0")
            if cfo > ni: score+=1; details.append("✅ CFO > NI (應計項目佳)")
            
            # ROA YoY
            p_ni = get_p(self.inc, 'NET_INCOME')
            p_assets = get_p(self.bs, 'ASSETS')
            if p_assets and assets and (ni/assets) > (p_ni/p_assets): 
                score+=1; details.append("✅ ROA YoY > 0")

            # 2. 財務結構
            # 槓桿 (Long Term Debt / Assets)
            # Long Term Debt = Total Liab - Current Liab
            tot_liab = get(self.bs, 'LIABILITIES')
            cur_liab = get(self.bs, 'CURRENT_LIABILITIES')
            lt_debt = tot_liab - cur_liab
            
            p_tot_liab = get_p(self.bs, 'LIABILITIES')
            p_cur_liab = get_p(self.bs, 'CURRENT_LIABILITIES')
            
            if p_assets and assets:
                p_lt_debt = p_tot_liab - p_cur_liab
                if (lt_debt/assets) <= (p_lt_debt/p_assets): 
                    score+=1; details.append("✅ 長期負債比率下降")

            # 流動比 (Current Assets / Current Liab)
            cur_assets = get(self.bs, 'CURRENT_ASSETS')
            p_cur_assets = get_p(self.bs, 'CURRENT_ASSETS')
            
            if cur_liab and p_cur_liab and p_cur_assets:
                if (cur_assets/cur_liab) > (p_cur_assets/p_cur_liab):
                    score+=1; details.append("✅ 流動比率上升")
            
            # 股本 (Common Stock)
            stock = get(self.bs, 'COMMON_STOCK')
            p_stock = get_p(self.bs, 'COMMON_STOCK')
            if p_stock:
                if stock <= p_stock * 1.05: score+=1; details.append("✅ 無顯著現金增資")
            else:
                score+=1 # 無數據從寬
                details.append("⚠️ 無股本數據，預設通過")

            # 3. 營運效率
            # 毛利率 (Gross Margin)
            rev = get(self.inc, 'REVENUE')
            cost = get(self.inc, 'OPERATING_COSTS')
            p_rev = get_p(self.inc, 'REVENUE')
            p_cost = get_p(self.inc, 'OPERATING_COSTS')
            
            # 檢查是否有毛利數據 (金融業可能沒有 cost)
            has_gm_data = rev > 0 and cost > 0 and p_rev > 0
            if has_gm_data:
                gm = (rev - cost) / rev
                p_gm = (p_rev - p_cost) / p_rev
                if gm > p_gm: score+=1; details.append("✅ 毛利率提升")
            else:
                # 若無毛利資料，有些策略會看營業利益率，這裡依報告F-Score定義若無則不給分或跳過
                # 為避免因為沒有 OperatingCosts 就扣分，這裡若該產業無此欄位可視為 N/A
                pass

            # 資產週轉率 (Revenue / Assets)
            if assets and p_assets and p_rev:
                if (rev/assets) > (p_rev/p_assets): score+=1; details.append("✅ 資產週轉率提升")

        except Exception as e:
            details.append(f"⚠️ 計算異常: {str(e)}")
            
        return score, details

    def calculate_z_score(self):
        try:
            if self.bs.empty: return None, "無數據"
            
            # 1. 產業檢查
            sector = self.info.get('sector', '')
            if 'Financial' in sector or 'Bank' in sector: return None, "金融業不適用"

            curr_date = self.bs.index[0]
            
            # Helper
            def get(df, key): return self._get_value_smart(df, curr_date, key)

            # 2. 準備五大變數
            ta = get(self.bs, 'ASSETS')
            tl = get(self.bs, 'LIABILITIES')
            ca = get(self.bs, 'CURRENT_ASSETS')
            cl = get(self.bs, 'CURRENT_LIABILITIES')
            re = get(self.bs, 'RETAINED_EARNINGS')
            rev = get(self.inc, 'REVENUE')
            
            # EBIT 估算
            ebit = get(self.inc, 'EBIT')
            if ebit == 0: # 若無直接欄位，用稅前+利息
                ebit = get(self.inc, 'PRE_TAX_INCOME') + get(self.inc, 'INTEREST_EXPENSE')
            
            mc = self.info.get('marketCap', 0)
            
            # 3. 防呆檢查
            if ta == 0 or tl == 0: return None, "資產或負債為0，無法計算"
            
            # 4. 計算權重
            x1 = (ca - cl) / ta
            x2 = re / ta
            x3 = ebit / ta
            x4 = mc / tl
            x5 = rev / ta
            
            z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
            return z, "計算完成"
            
        except Exception as e:
            return None, f"計算失敗: {str(e)}"
            
