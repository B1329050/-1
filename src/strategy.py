# src/strategy.py
import pandas as pd

def generate_signals(f_score, z_score, info, metrics_details):
    """
    綜合評分卡邏輯
    """
    total_score = 0
    signal_reasons = []

    # 1. 基本面體質 (F-Score)
    if f_score >= 8:
        total_score += 2
        signal_reasons.append("✅ F-Score >= 8 (+2)")
    elif 5 <= f_score <= 7:
        total_score += 1
        signal_reasons.append("🔹 F-Score 5~7 (+1)")
    elif f_score <= 3:
        total_score -= 2
        signal_reasons.append("⚠️ F-Score <= 3 (-2)")

    # 2. 破產風險 (Z-Score)
    if z_score is not None:
        if z_score > 2.99:
            total_score += 1
            signal_reasons.append("✅ Z-Score 安全區 (+1)")
        elif z_score < 1.81:
            total_score -= 3
            signal_reasons.append("💀 Z-Score 風險區 (-3)")
    else:
        signal_reasons.append("ℹ️ Z-Score 不適用或數據缺失 (跳過)")

    # 3. 相對估值 (PE Ratio)
    pe = info.get('trailingPE', None)
    if pe:
        if pe < 12:
            total_score += 1
            signal_reasons.append("✅ PE < 12 (低估) (+1)")
        elif pe > 25:
            total_score -= 1
            signal_reasons.append("⚠️ PE > 25 (過熱) (-1)")

    # 4. 資產價值 (PB Ratio)
    pb = info.get('priceToBook', None)
    if pb and pb < 1.0:
        total_score += 1
        signal_reasons.append("✅ PB < 1.0 (深度價值) (+1)")
        
    # 生成最終建議
    action = "觀望 (Watch)"
    color = "orange" # Streamlit color
    
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
    針對資訊延遲的下單建議
    """
    if "Buy" in action:
        return """
        **建議下單策略 (Latency Defense):**
        1. **盤後掛單 (EOD Strategy):** 今日收盤後，掛入明日開盤前限價單。
        2. **尾盤集合競價 (13:25 ROD):** 若接近 13:25，可掛入 **ROD 限價單** (價格設為目前價 +1% 以確保成交但防暴漲)。
        ⚠️ **絕對禁止使用市價單 (Market Order)**，以免因 20 分鐘延遲數據導致嚴重滑價。
        """
    return "無操作建議"
