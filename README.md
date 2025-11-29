# 📈 TW-Quant: 台股量化交易決策系統

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)
![FinMind](https://img.shields.io/badge/Data-FinMind-green)

## 📖 專案簡介 (Project Overview)

本專案是一個基於 Python 與 Streamlit 構建的台股量化分析工具。核心邏輯嚴格遵循研究報告**《構建基於開源資源與華爾街指標的台股量化交易系統：克服資訊延遲與數據整合之深度研究》**。

系統旨在解決零售投資人使用免費數據源時面臨的「資訊延遲」與「數據碎片化」問題，透過自動化的 ETL 流程與在地化的財務指標運算，提供客觀的投資決策輔助。

## 🚀 核心功能 (Key Features)

本系統實作了報告中提出的**「估值加扣分評分卡 (Valuation Scorecard)」**模型：

* **基本面體質檢測 (Piotroski F-Score):**
    * 完整實作 9 大指標檢定，包含獲利性、安全性與營運效率。
    * 針對台股特性優化（如應計項目與現金增資檢查）。
* **破產風險預警 (Altman Z-Score):**
    * 在地化會計科目映射（Mapping），精準計算台灣財報數據。
    * 內建產業濾網，自動排除金融業以避免誤判。
* **營收動能分析 (Revenue Momentum):**
    * 整合高頻月營收數據，計算 MoM (月增率) 與 YoY (年增率)。
* **延遲對策 (Latency Defense):**
    * 針對免費 API 的 20 分鐘延遲，提供「盤後佈局」與「尾盤 ROD」下單策略建議。

## 🛠️ 技術架構 (Tech Stack)

* **語言:** Python
* **框架:** Streamlit (Web UI)
* **數據源:**
    * **FinMind:** 獲取台股財報（資產負債表、損益表、現金流量表、月營收）。
    * **yfinance:** 獲取歷史股價與技術指標數據。
* **數據處理:** Pandas, NumPy
* **視覺化:** Plotly

## 📂 專案結構 (Directory Structure)

```text
TW-Quant/
├── main.py              # 系統入口與主介面
├── requirements.txt     # 相依套件清單
├── src/                 # 核心邏輯模組
│   ├── config.py        # 會計科目映射與設定
│   ├── data_loader.py   # 數據獲取與快取機制 (ETL)
│   ├── metrics.py       # F-Score, Z-Score, 營收計算引擎
│   └── strategy.py      # 估值評分卡與交易訊號生成
└── pages/
    └── glossary.py      # 系統說明書與名詞解釋
