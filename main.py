import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

st.set_page_config(page_title="台股在地化量化系統", layout="wide")
st.title("🇹🇼 台股在地化量化決策系統")
st.markdown("### 整合月營收動能、三大法人籌碼與大師估值模型")

with st.sidebar:
    st.header("系統設定")
    stock_id = st.text_input("股票代號", value="2330")
    if "FINMIND_TOKEN" in st.secrets:
        token = st.secrets["FINMIND_TOKEN"]
        st.success("✅ Token 已載入")
    else:
        token = st.text_input("FinMind Token", type="password")
    run_btn = st.button("執行在地化分析", type="primary")

if run_btn:
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在分析 {stock_id} (含籌碼/營收/財報)..."):
        try:
            # 1. 獲取數據 (含籌碼 chip)
            price_df, info = engine.get_price_data(stock_id)
            bs, inc, cf, rev, div, chip = engine.get_financial_data(stock_id)
            
            if bs.empty or inc.empty:
                st.error("❌ 數據不足 (可能為新股或資料庫缺漏)")
                st.stop()
            
            # 2. 計算指標
            calculator = MetricCalculator(bs, inc, cf, rev, div, chip, info)
            
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            mom, yoy = calculator.calculate_revenue_growth()
            guru_metrics = calculator.calculate_guru_metrics()
            chip_metrics = calculator.calculate_chip_metrics() # [新增]
            
            # 3. 策略生成
            total_score, action, color, reasons = generate_signals(
                f_score, z_score, info, mom, yoy, guru_metrics, chip_metrics
            )
            
            # --- UI 顯示 ---
            st.divider()
            
            # A. 核心決策
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"決策評級: :{color}[{action}] (總分 {total_score})")
                if "Buy" in action or "Hold" in action:
                    st.info(suggest_order_type(action), icon="🛡️")
            with c2:
                # 葛拉漢估值顯示
                graham = guru_metrics.get('Graham Number', 0)
                price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
                delta_val = f"{((price-graham)/graham)*100:.1f}% (溢價)" if (graham and price) else None
                st.metric("葛拉漢估值 (5年平均)", f"{graham:.1f}", delta=delta_val, delta_color="inverse")

            st.divider()
            
            # B. 在地化因子儀表板 (籌碼 + 營收)
            st.subheader("📊 台股在地化因子")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("外資動向", "連買 3 日" if chip_metrics.get("Foreign Consecutive Buy") else "無連續買超")
            m2.metric("投信動向", "🔥 認養中" if chip_metrics.get("Trust Active Buy") else "無顯著佈局", 
                      help="條件: 近期買超且為中小型股")
            m3.metric("營收 YoY", f"{yoy:.1f}%" if yoy is not None else "N/A", delta_color="normal")
            m4.metric("營收 MoM", f"{mom:.1f}%" if mom is not None else "N/A", delta_color="normal")

           # ... (前段代碼不變) ...

            # C. 大師指標
            st.subheader("🎓 華爾街大師指標")
            g1, g2, g3 = st.columns(3)
            
            # [修復點] 先檢查 PEG 是否為 None，再決定顯示內容
            peg = guru_metrics.get('Lynch PEG')
            peg_display = f"{peg:.2f}" if peg is not None else "N/A (無PE)"
            
            g1.metric("林區 PEG", peg_display, help="< 1.0 合理，N/A 代表目前虧損或無本益比")
            
            # 神奇公式顯示優化
            roc_val = guru_metrics.get('Magic ROC', 0)
            ey_val = guru_metrics.get('Magic EY', 0)
            g2.metric("神奇公式", f"ROC {roc_val:.1f}%", help=f"盈餘殖利率 (EY): {ey_val:.1f}%")
            
            g3.metric("F-Score", f"{f_score}/9")

            # ... (後段代碼不變) ...
            # 詳細理由
            st.markdown("#### 📝 評分依據")
            for r in reasons: st.write(r)

            # K線圖
            if not price_df.empty:
                st.plotly_chart(go.Figure(data=[go.Candlestick(x=price_df.index, open=price_df['Open'], high=price_df['High'], low=price_df['Low'], close=price_df['Close'])]), use_container_width=True)

        except Exception as e:
            st.error(f"分析失敗: {e}")
