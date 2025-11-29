import pandas as pd

def generate_signals(f_score, z_score, info, mom, yoy, guru_metrics, chip_metrics):
    """
    台股在地化綜合評分 (Localized Scoring)
    """
    total_score = 0
    signal_reasons = []

    # 1. F-Score (基本面體質)
    if f_score >= 8:
        total_score += 2
        signal_reasons.append(f"✅ F-Score {f_score} (體質強健 +2)")
    elif f_score <= 3:
        total_score -= 2
        signal_reasons.append(f"⚠️ F-Score {f_score} (體質衰退 -2)")

    # 2. Z-Score (破產風險)
    if z_score is not None and z_score < 1.81:
        total_score -= 3
        signal_reasons.append(f"💀 Z-Score {z_score:.2f} (破產風險 -3)")

    # 3. 葛拉漢防禦 (價值)
    price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
    graham_num = guru_metrics.get('Graham Number', 0)
    curr_ratio = guru_metrics.get('Current Ratio', 0)
    if price > 0 and graham_num > 0 and price < graham_num:
        if curr_ratio > 1.5:
            total_score += 2
            signal_reasons.append(f"💎 葛拉漢價值股 (價 < {graham_num:.1f} 且 流動比 > 1.5) (+2)")
        else:
            total_score += 1
            signal_reasons.append(f"🔹 價格低於葛拉漢數 {graham_num:.1f} (+1)")

    # 4. 林區 PEG (成長價值)
    peg = guru_metrics.get('Lynch PEG')
    if peg is not None:
        if peg < 0.5: total_score += 2; signal_reasons.append(f"🚀 林區 PEG {peg:.2f} < 0.5 (極度低估 +2)")
        elif peg < 1.0: total_score += 1; signal_reasons.append(f"🔹 林區 PEG {peg:.2f} < 1.0 (合理 +1)")
        elif peg > 2.0: total_score -= 1; signal_reasons.append(f"⚠️ 林區 PEG {peg:.2f} > 2.0 (過熱 -1)")

    # 5. 神奇公式 (好公司+便宜)
    roc = guru_metrics.get('Magic ROC', 0)
    ey = guru_metrics.get('Magic EY', 0)
    if roc > 20 and ey > 5:
        total_score += 2
        signal_reasons.append(f"✨ 神奇公式 (ROC {roc:.1f}% > 20, EY {ey:.1f}% > 5) (+2)")

    # --- [在地化修正] 月營收與籌碼 ---
    
    # 6. 月營收動能 (Revenue Momentum) 
    if yoy is not None and mom is not None:
        if yoy > 20 and mom > 0:
            total_score += 2
            signal_reasons.append(f"🔥 營收雙強 (YoY {yoy:.1f}% > 20% & MoM > 0) (台股核心動能 +2)")
        elif yoy > 20:
            total_score += 1
            signal_reasons.append(f"📈 營收年增 {yoy:.1f}% > 20% (+1)")

    # 7. 籌碼面 (Chip Alpha) 
    if chip_metrics:
        if chip_metrics.get("Foreign Consecutive Buy"):
            total_score += 1
            signal_reasons.append("💰 外資連續 3 日買超 (趨勢推動 +1)")
        if chip_metrics.get("Trust Active Buy"):
            total_score += 2
            signal_reasons.append("🚀 投信積極認養中小型股 (作帳行情 +2)")

    # 8. 流動性陷阱 (Liquidity Trap) 
    avg_vol = info.get('averageVolume', 0)
    if avg_vol > 0 and avg_vol < 500000: # 小於 500 張
        total_score -= 2
        signal_reasons.append("⚠️ 日均量 < 500 張 (流動性陷阱 -2)")

    # 最終決策
    action = "觀望 (Watch)"
    color = "orange"
    if total_score >= 5:
        action = "強力買進 (Strong Buy)"; color = "green"
    elif 3 <= total_score <= 4:
        action = "買進/持有 (Buy/Hold)"; color = "blue"
    elif total_score < 0:
        action = "賣出/避開 (Sell/Avoid)"; color = "red"
        
    return total_score, action, color, signal_reasons

def suggest_order_type(action):
    # [cite: 346-351, 394] 交易成本與漲停對策
    if "Buy" in action or "Hold" in action:
        return """
        **🇹🇼 台股在地化操作建議:**
        1. **避開開盤 (08:30-09:00):** 虛掛單多，易受騙。
        2. **推薦盤後/尾盤:** 13:25 後掛 **ROD 限價單**，規避盤中波動。
        3. **注意漲停:** 若接近漲停 (+9%)，需評估是否鎖死買不到。
        4. **成本控制:** 買賣成本約 0.5%，切勿頻繁當沖。
        """
    return ""
