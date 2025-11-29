# src/strategy.py
import pandas as pd

def generate_signals(f_score, z_score, info, mom, yoy, guru_metrics):
    """
    整合大師指標的綜合評分
    """
    total_score = 0
    signal_reasons = []

    # 1. F-Score
    if f_score >= 8:
        total_score += 2
        signal_reasons.append(f"✅ F-Score {f_score} (體質強健 +2)")
    elif f_score <= 3:
        total_score -= 2
        signal_reasons.append(f"⚠️ F-Score {f_score} (體質衰退 -2)")

    # 2. Z-Score
    if z_score is not None and z_score < 1.81:
        total_score -= 3
        signal_reasons.append(f"💀 Z-Score {z_score:.2f} (破產風險 -3)")

    # 3. 葛拉漢估值 [報告 2.1.1]
    price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
    graham_num = guru_metrics.get('Graham Number', 0)
    if price > 0 and graham_num > 0:
        if price < graham_num * 0.8: # 給予 20% 安全邊際
            total_score += 2
            signal_reasons.append(f"💎 股價 ({price}) 低於葛拉漢數 ({graham_num:.1f}) (深度價值 +2)")
    
    # 4. 林區 PEG [報告 2.2.1]
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

    # 5. 神奇公式 ROC [報告 2.3.1]
    roc = guru_metrics.get('Magic ROC', 0)
    if roc > 30: # 30% 以上視為極高效率
        total_score += 1
        signal_reasons.append(f"✨ 資本報酬率 (ROC) {roc:.1f}% > 30% (資金效率極佳 +1)")

    # 6. 營收動能
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
