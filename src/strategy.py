import pandas as pd

def generate_signals(f_score, z_score, info, mom, yoy, guru_metrics):
    """
    整合大師指標的綜合評分 (符合研究報告標準)
    """
    total_score = 0
    signal_reasons = []

    # 1. F-Score (皮爾托斯基) [cite: 64]
    if f_score >= 8:
        total_score += 2
        signal_reasons.append(f"✅ F-Score {f_score} (體質強健 +2)")
    elif f_score <= 3:
        total_score -= 2
        signal_reasons.append(f"⚠️ F-Score {f_score} (體質衰退 -2)")

    # 2. Z-Score (奧特曼)
    if z_score is not None and z_score < 1.81:
        total_score -= 3
        signal_reasons.append(f"💀 Z-Score {z_score:.2f} (破產風險 -3)")

    # 3. 葛拉漢防禦型策略 [cite: 9, 26]
    # 修正：使用 5 年平均 EPS 算出的葛拉漢數
    price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
    graham_num = guru_metrics.get('Graham Number', 0)
    curr_ratio = guru_metrics.get('Current Ratio', 0)
    
    if price > 0 and graham_num > 0:
        # 價格低於價值 (安全邊際) 且 財務健康 (流動比率 > 1.5, 報告標準為 2.0 但可適度放寬)
        if price < graham_num:
            if curr_ratio > 1.5:
                total_score += 2
                signal_reasons.append(f"💎 葛拉漢價值股 (價 < {graham_num:.1f} 且 流動比 {curr_ratio:.1f} > 1.5) (+2)")
            else:
                # 便宜但不夠健康
                total_score += 1
                signal_reasons.append(f"🔹 價格低於葛拉漢數 {graham_num:.1f} (但流動比偏低) (+1)")

    # 4. 林區 PEG (Yield-Adjusted) [cite: 36]
    peg = guru_metrics.get('Lynch PEG')
    if peg is not None:
        if peg < 0.5:
            total_score += 2
            signal_reasons.append(f"🚀 林區 PEG {peg:.2f} < 0.5 (極度低估 +2)")
        elif peg < 1.0:
            total_score += 1
            signal_reasons.append(f"🔹 林區 PEG {peg:.2f} < 1.0 (合理價格 +1)")
        elif peg > 2.0:
            total_score -= 1
            signal_reasons.append(f"⚠️ 林區 PEG {peg:.2f} > 2.0 (成長跟不上估值 -1)")

    # 5. 神奇公式 (Magic Formula) [cite: 55-60]
    # 修正：同時檢查 ROC (品質) 與 Earnings Yield (價格)
    roc = guru_metrics.get('Magic ROC', 0)
    ey = guru_metrics.get('Magic EY', 0)
    
    # 門檻設定：ROC > 20% (相當優秀) 且 EY > 5% (相當於本益比 < 20)
    if roc > 20 and ey > 5:
        total_score += 2
        signal_reasons.append(f"✨ 神奇公式選股 (ROC {roc:.1f}% > 20 且 EY {ey:.1f}% > 5) (+2)")
    elif roc > 20:
        # 只符合好公司，但不便宜 -> 不加分 (避免買貴)
        signal_reasons.append(f"🔸 神奇公式: 公司優質 (ROC {roc:.1f}%) 但不夠便宜 (EY {ey:.1f}%)")

    # 6. 營收動能 [cite: 108] (雖然報告 2.3.1 是講爬蟲，但營收動能符合成長股邏輯)
    if yoy and yoy > 20:
        total_score += 1
        signal_reasons.append(f"🔥 營收年增 {yoy:.1f}% > 20% (動能強勁 +1)")

    # 最終決策
    action = "觀望 (Watch)"
    color = "orange"
    if total_score >= 5:
        action = "強力買進 (Strong Buy)"
        color = "green"
    elif 3 <= total_score <= 4:
        action = "買進/持有 (Buy/Hold)"
        color = "blue"
    elif total_score < 0:
        action = "賣出/避開 (Sell/Avoid)"
        color = "red"
        
    return total_score, action, color, signal_reasons

def suggest_order_type(action):
    if "Buy" in action or "Hold" in action:
        return "**建議操作:** 依照報告建議，因應免費數據延遲，請使用 **盤後掛單** 或 **尾盤 ROD 限價單**。"
    return ""
