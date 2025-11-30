import pandas as pd

def generate_signals(f_score, z_score, info, mom, yoy, guru_metrics, chip_metrics, margin_metrics):
    """
    台股在地化綜合評分 (透明化顯示版)
    """
    total_score = 0
    signal_reasons = []

    # 1. F-Score
    if f_score >= 8: total_score += 2; signal_reasons.append(f"✅ F-Score {f_score} (體質強健 +2)")
    elif f_score <= 3: total_score -= 2; signal_reasons.append(f"⚠️ F-Score {f_score} (體質衰退 -2)")

    # 2. Z-Score
    if z_score is not None and z_score < 1.81: total_score -= 3; signal_reasons.append(f"💀 Z-Score {z_score:.2f} (破產風險 -3)")

    # 3. 葛拉漢 & NCAV
    price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
    graham_num = guru_metrics.get('Graham Number', 0)
    ncav = guru_metrics.get('NCAV', 0)
    
    if price > 0:
        if ncav > 0 and price < ncav * 0.66:
            total_score += 3
            signal_reasons.append(f"💎 股價 < 0.66 * NCAV (深度價值) (+3)")
        elif graham_num > 0 and price < graham_num:
            if guru_metrics.get('Current Ratio', 0) > 1.5:
                total_score += 2; signal_reasons.append(f"💎 價格低於葛拉漢數且體質佳 (+2)")
            else:
                total_score += 1; signal_reasons.append(f"🔹 價格低於葛拉漢數 (+1)")

    # 4. 林區 PEG
    peg = guru_metrics.get('Lynch PEG')
    if peg is not None:
        if peg < 0.5: total_score += 2; signal_reasons.append(f"🚀 PEG {peg:.2f} < 0.5 (極低估 +2)")
        elif peg < 1.0: total_score += 1; signal_reasons.append(f"🔹 PEG {peg:.2f} < 1.0 (合理 +1)")
        elif peg > 2.0: total_score -= 1; signal_reasons.append(f"⚠️ PEG {peg:.2f} > 2.0 (過熱 -1)")

    # 5. 神奇公式
    roc = guru_metrics.get('Magic ROC', 0)
    ey = guru_metrics.get('Magic EY', 0)
    if roc > 20 and ey > 5:
        total_score += 2; signal_reasons.append(f"✨ 神奇公式 (ROC>20, EY>5) (+2)")

    # 6. 營收動能
    if yoy is not None and mom is not None:
        if yoy > 20 and mom > 0: total_score += 2; signal_reasons.append(f"🔥 營收雙強 (YoY>20% & MoM>0) (+2)")
        elif yoy > 20: total_score += 1; signal_reasons.append(f"📈 營收年增 {yoy:.1f}% (+1)")

    # 7. 籌碼面 (更新邏輯)
    if chip_metrics:
        # 外資連買 (策略加分)
        if chip_metrics.get("Foreign Consecutive"): 
            total_score += 1
            signal_reasons.append("💰 外資連續 3 日買超 (+1)")
        
        # 投信認養 (策略加分)
        if chip_metrics.get("Trust Active Buy"): 
            total_score += 2
            signal_reasons.append("🚀 投信積極認養 (+2)")
        
        # [新增] 若外資賣超太多，給予警示 (但不一定要扣分，視策略而定)
        f_net = chip_metrics.get("Foreign Net (3d)", 0)
        if f_net < -5000000: # 賣超 5000 張
             signal_reasons.append(f"⚠️ 外資近3日大賣 {int(abs(f_net)//1000)} 張")

    # 8. 融資
    if margin_metrics:
        margin_up = margin_metrics.get("Margin Increasing")
        if margin_up: signal_reasons.append("⚠️ 融資餘額增加 (散戶進場)")
        else: signal_reasons.append("🛡️ 融資餘額減少 (籌碼安定)")

    # 9. 流動性
    avg_vol = info.get('averageVolume', 0)
    if avg_vol > 0 and avg_vol < 500000: total_score -= 2; signal_reasons.append("⚠️ 低流動性 (-2)")

    action = "觀望 (Watch)"; color = "orange"
    if total_score >= 5: action = "強力買進 (Strong Buy)"; color = "green"
    elif 3 <= total_score <= 4: action = "買進/持有 (Buy/Hold)"; color = "blue"
    elif total_score < 0: action = "賣出/避開 (Sell/Avoid)"; color = "red"
        
    return total_score, action, color, signal_reasons

def suggest_order_type(action):
    if "Buy" in action or "Hold" in action:
        return "**在地化建議:** 盤後掛單或尾盤 ROD，避開開盤波動。注意成交量。"
    return ""
