# src/config.py

DATASETS = {
    'BALANCE_SHEET': 'TaiwanStockBalanceSheet',
    'INCOME_STATEMENT': 'TaiwanStockFinancialStatements',
    'CASH_FLOW': 'TaiwanStockCashFlows',
    'REVENUE': 'TaiwanStockMonthRevenue',
    'DIVIDEND': 'TaiwanStockDividend',
    'INSTITUTIONAL': 'TaiwanStockInstitutionalInvestorsBuySell' # [新增] 三大法人
}

# 會計科目映射 (支援 FinMind 多種命名可能)
MAPPING = {
    # --- 資產負債表 ---
    'ASSETS': ['TotalAssets', 'Assets'], 
    'LIABILITIES': ['TotalLiabilities', 'Liabilities'],
    'CURRENT_ASSETS': ['CurrentAssets'],
    'CURRENT_LIABILITIES': ['CurrentLiabilities'],
    'NON_CURRENT_LIABILITIES': ['NonCurrentLiabilities'],
    'RETAINED_EARNINGS': ['RetainedEarnings', 'UnappropriatedRetainedEarnings', 'RetainedEarningsAccumulatedDeficit'], 
    'EQUITY': ['TotalEquity', 'Equity', 'StockholdersEquity'],
    'COMMON_STOCK': ['CommonStock', 'OrdinaryShares', 'CapitalStock'],
    'FIXED_ASSETS': ['NonCurrentAssets', 'FixedAssets', 'PropertyPlantAndEquipment'], # 用於神奇公式
    'CASH': ['CashAndCashEquivalents', 'Cash'], # 用於企業價值 EV 計算

    # --- 損益表 ---
    'REVENUE': ['Revenue', 'OperatingRevenue', 'TotalOperatingRevenue'],
    'OPERATING_COSTS': ['OperatingCosts', 'CostOfRevenue'],
    'OPERATING_INCOME': ['OperatingIncome'],
    'PRE_TAX_INCOME': ['PreTaxIncome', 'IncomeBeforeTax'],
    'NET_INCOME': ['IncomeAfterTaxes', 'NetIncome', 'ProfitLoss'],
    'INTEREST_EXPENSE': ['InterestExpense', 'FinanceCosts'],
    'EPS': ['EPS', 'EarningsPerShare'],
    'EBIT': ['EBIT'],

    # --- 現金流量表 ---
    'OPERATING_CASH_FLOW': ['CashFlowsFromOperatingActivities', 'NetCashProvidedByUsedInOperatingActivities']
}

# 金融業代碼 (不適用 Z-Score)
EXCLUDED_SECTORS = ['28']
