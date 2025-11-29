# src/config.py

# FinMind 資料集名稱
DATASETS = {
    'BALANCE_SHEET': 'TaiwanStockBalanceSheet',
    'INCOME_STATEMENT': 'TaiwanStockFinancialStatements', # 注意：FinMind API 有時容許複數，若失敗 data_loader 會處理
    'CASH_FLOW': 'TaiwanStockCashFlows',
    'REVENUE': 'TaiwanStockMonthRevenue'
}

# 會計科目映射表 (Mapping)
# 修改為：主要欄位 -> [可能的 FinMind 欄位名稱列表]
# 程式會依序尋找，直到找到為止
MAPPING = {
    # 資產負債表
    'ASSETS': ['TotalAssets', 'Assets'], 
    'LIABILITIES': ['TotalLiabilities', 'Liabilities'],
    'CURRENT_ASSETS': ['CurrentAssets'],
    'CURRENT_LIABILITIES': ['CurrentLiabilities'],
    'NON_CURRENT_LIABILITIES': ['NonCurrentLiabilities'],
    'RETAINED_EARNINGS': ['RetainedEarnings', 'UnappropriatedRetainedEarnings', 'RetainedEarningsAccumulatedDeficit'], 
    'EQUITY': ['TotalEquity', 'Equity'],
    'COMMON_STOCK': ['CommonStock', 'OrdinaryShares', 'CapitalStock'],

    # 損益表
    'REVENUE': ['Revenue', 'OperatingRevenue', 'TotalOperatingRevenue'], # 修正關鍵：加入 OperatingRevenue
    'OPERATING_COSTS': ['OperatingCosts', 'CostOfRevenue'],
    'OPERATING_INCOME': ['OperatingIncome'],
    'PRE_TAX_INCOME': ['PreTaxIncome', 'IncomeBeforeTax'],
    'NET_INCOME': ['IncomeAfterTaxes', 'NetIncome', 'ProfitLoss'],
    'INTEREST_EXPENSE': ['InterestExpense', 'FinanceCosts'],
    'EBIT': ['EBIT'], # 若無此欄位，metrics.py 會自行估算

    # 現金流量表
    'OPERATING_CASH_FLOW': ['CashFlowsFromOperatingActivities', 'NetCashProvidedByUsedInOperatingActivities']
}

# 產業過濾器 (金融保險業 28 開頭不適用 Z-Score)
EXCLUDED_SECTORS = ['28']
