# src/config.py

DATASETS = {
    'BALANCE_SHEET': 'TaiwanStockBalanceSheet',
    'INCOME_STATEMENT': 'TaiwanStockFinancialStatements',
    'CASH_FLOW': 'TaiwanStockCashFlows',
    'REVENUE': 'TaiwanStockMonthRevenue',
    'DIVIDEND': 'TaiwanStockDividend' # [新增] 股利政策表
}

MAPPING = {
    # --- 資產負債表 ---
    'ASSETS': ['TotalAssets', 'Assets'], 
    'LIABILITIES': ['TotalLiabilities', 'Liabilities'],
    'CURRENT_ASSETS': ['CurrentAssets'],
    'CURRENT_LIABILITIES': ['CurrentLiabilities'],
    'NON_CURRENT_LIABILITIES': ['NonCurrentLiabilities'],
    'RETAINED_EARNINGS': ['RetainedEarnings', 'UnappropriatedRetainedEarnings'], 
    'EQUITY': ['TotalEquity', 'Equity', 'StockholdersEquity'], # 修正權益
    'COMMON_STOCK': ['CommonStock', 'OrdinaryShares', 'CapitalStock'],
    'FIXED_ASSETS': ['NonCurrentAssets', 'FixedAssets'], # 用於神奇公式

    # --- 損益表 ---
    'REVENUE': ['Revenue', 'OperatingRevenue', 'TotalOperatingRevenue'],
    'OPERATING_COSTS': ['OperatingCosts', 'CostOfRevenue'],
    'OPERATING_INCOME': ['OperatingIncome'],
    'PRE_TAX_INCOME': ['PreTaxIncome', 'IncomeBeforeTax'],
    'NET_INCOME': ['IncomeAfterTaxes', 'NetIncome', 'ProfitLoss'],
    'INTEREST_EXPENSE': ['InterestExpense', 'FinanceCosts'],
    'EPS': ['EPS', 'EarningsPerShare'], # 用於葛拉漢數
    'EBIT': ['EBIT'],

    # --- 現金流量表 ---
    'OPERATING_CASH_FLOW': ['CashFlowsFromOperatingActivities', 'NetCashProvidedByUsedInOperatingActivities'],
    
    # --- 股利表 ---
    'CASH_DIVIDEND': ['CashEarningsDistribution', 'CashDividend'], # 現金股利
    'STOCK_DIVIDEND': ['StockEarningsDistribution', 'StockDividend'] # 股票股利
}

EXCLUDED_SECTORS = ['28']
