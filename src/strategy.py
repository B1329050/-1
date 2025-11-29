# src/strategy.py
import pandas as pd

def generate_signals(f_score, z_score, info, mom, yoy):
    """
    嚴格執行 [研究報告 表2：台股輔助買賣程式之估值加扣分邏輯表]
    """
    total_score = 0
    signal_reasons = []

    # --- 1. 基本面體質 (F-Score) ---
    if f_score >= 8:
        total_score += 2
        signal_reasons.append(f"✅ F-Score {f_score} (體質強健 +2)")
    elif 5 <= f_score <= 7:
        total_score += 1
        signal_reasons.append(f"🔹 F-Score {f_score} (體質穩健 +1)")
    elif f_score <= 3:
        total_score -= 2
        signal_reasons.append(f"⚠️ F-Score {f_score} (體質衰退 -2)")
    else:
        signal_reasons.append(f"🔸 F-Score {f_score} (中性 0)")

    # --- 2. 破產風險 (Z-Score) ---
    if z_score is not None:
        if z_score > 2.99:
            total_score += 1
            signal_reasons.append(f"✅ Z-Score {z_score:.2f} (安全區域 +1)")
        elif z_score < 1.81:
            total_score -= 3
            signal_reasons.append(f"💀 Z-Score {z_score:.2f} (困境區域 -3)")
        else:
            signal_reasons.append(f"🔸 Z-Score {z_score:.2f} (灰色區域 0)")
    else:
        signal_reasons.append("ℹ️ Z-Score 不適用 (金融業或數據不足)")

    # --- 3. 相對估值 (PE Ratio) ---
    pe = info.get('trailingPE', None)
    if pe:
        if pe < 12:
            total_score += 1
            signal_reasons.append(f"✅ 本益比 {pe:.1f} < 12 (價格低估 +1)")
        elif pe > 25:
            total_score -= 1
            signal_reasons.append(f"⚠️ 本益比 {pe:.1f} > 25 (價格過高 -1)")

    # --- 4. 資產價值 (PB Ratio) ---
    pb = info.get('priceToBook', None)
    if pb and pb < 1.0:
        total_score += 1
        signal_reasons.append(f"✅ 股價淨值比 {pb:.2f} < 1.0 (深度價值 +1)")

    # --- 5. 成長動能 (Revenue) [報告 2.3.1 重點] ---
    if yoy is not None and mom is not None:
        if yoy > 20:
            total_score += 1
            signal_reasons.append(f"🚀 營收年增率 {yoy:.1f}% > 20% (動能強勁 +1)")
        if mom > 10:
            total_score += 1
            signal_reasons.append(f"🔥 營收月增率 {mom:.1f}% > 10% (加速升溫 +1)")
    else:
        signal_reasons.append("ℹ️ 無法取得最新營收數據 (略過動能加分)")

    # --- 6. 財報操弄 (M-Score) [報告 3.3] ---
    # 註：完整 M-Score 需 8 個變數，為避免數據不足導致誤判，
    # 此處僅作為提醒，若未來數據庫擴充應補上：若 M-Score > -1.78 則 total_score = -99 (直接剔除)
    
    # --- 生成最終決策 (報告 4.2) ---
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
    """
    [嚴格執行報告 5.2 & 5.3] 延遲對策
    """
    if "Buy" in action or "Hold" in action:
        return """
        **報告章節 5.2 執行策略:**
        * **盤後佈局 (EOD):** 由於使用免費 API 存在 20 分鐘延遲，嚴禁盤中市價單。
        * **建議操作:** 於今日盤後掛入明日開盤前 **限價單 (Limit Order)**。
        * **尾盤操作:** 若為 13:25，可掛入 **ROD** 單。
        """
    return "無操作建議"
