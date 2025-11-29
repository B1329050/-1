# src/config.py

# FinMind 資料集名稱對照
DATASETS = {
    'BALANCE_SHEET': 'TaiwanStockBalanceSheet',
    'INCOME_STATEMENT': 'TaiwanStockFinancialStatements',
    'CASH_FLOW': 'TaiwanStockCashFlows',
    'INSTITUTIONAL': 'TaiwanStockInstitutionalInvestorsBuySell',
    'REVENUE': 'TaiwanStockMonthRevenue'
}

# 會計科目映射表 (Mapping)
# 將 FinMind 的欄位名稱映射到程式內部使用的標準名稱
MAPPING = {
    'ASSETS': 'TotalAssets',                      # 資產總額
    'LIABILITIES': 'TotalLiabilities',            # 負債總額
    'CURRENT_ASSETS': 'CurrentAssets',            # 流動資產
    'CURRENT_LIABILITIES': 'CurrentLiabilities',  # 流動負債
    'NON_CURRENT_LIABILITIES': 'NonCurrentLiabilities', # 非流動負債
    'RETAINED_EARNINGS': 'RetainedEarnings',      # 保留盈餘 (Z-Score X2)
    'OPERATING_INCOME': 'OperatingIncome',        # 營業利益
    'PRE_TAX_INCOME': 'PreTaxIncome',             # 稅前淨利
    'NET_INCOME': 'IncomeAfterTaxes',             # 本期淨利
    'OPERATING_CASH_FLOW': 'CashFlowsFromOperatingActivities', # 營運現金流
    'REVENUE': 'Revenue',                         # 營收
    'INTEREST_EXPENSE': 'InterestExpense'         # 利息費用
}

# 產業過濾器
# 金融保險業 (28開頭) 不適用 Altman Z-Score
EXCLUDED_SECTORS = ['28']
