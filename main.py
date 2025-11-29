# main.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

st.set_page_config(page_title="台股大師量化系統", layout="wide")
st.title("📈 台股大師量化決策系統")
st.markdown("### 基於大師理論與科學驗證體系之深度優化版")

with st.sidebar:
    st.header("系統設定")
    stock_id = st.text_input("股票代號", value="2330")
    if "FINMIND_TOKEN" in st.secrets:
        token = st.secrets["FINMIND_TOKEN"]
        st.success("✅ Token 已載入")
    else:
        token = st.text_input("FinMind Token", type="password")
    run_btn = st.button("執行大師策略分析", type="primary")

if run_btn:
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在運算 {stock_id} 之大師指標..."):
        try:
            # 1. 獲取數據 (含股利)
            price_df, info = engine.get_price_data(stock_id)
            bs, inc, cf, rev, div = engine.get_financial_data(stock_id)
            
            if bs.empty or inc.empty:
                st.error("❌ 數據不足")
                st.stop()
            
            # 2. 計算指標
            calculator = MetricCalculator(bs, inc, cf, rev, div, info)
            
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            mom, yoy = calculator.calculate_revenue_growth()
            # [新增] 計算大師指標
            guru_metrics = calculator.calculate_guru_metrics()
            
            # 3. 策略生成
            total_score, action, color, reasons = generate_signals(f_score, z_score, info, mom, yoy, guru_metrics)
            
            # --- UI 顯示 ---
            st.divider()
            
            # 核心決策區
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"決策評級: :{color}[{action}] (總分 {total_score})")
                if "Buy" in action: st.info(suggest_order_type(action))
            with c2:
                graham = guru_metrics.get('Graham Number', 0)
                price = info.get('currentPrice', 0)
                st.metric("葛拉漢估值上限", f"{graham:.1f}", delta=f"{((price-graham)/graham)*100:.1f}% (溢價率)" if graham else None, delta_color="inverse")

            st.divider()
            
            # 大師指標儀表板
            st.subheader("🎓 大師策略儀表板")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("林區 PEG", f"{guru_metrics.get('Lynch PEG', 0):.2f}", help="< 1.0 為合理")
            g2.metric("神奇公式 ROC", f"{guru_metrics.get('Magic ROC', 0):.1f}%", help="資本回報率")
            g3.metric("F-Score", f"{f_score}/9", help="皮爾托斯基分數")
            g4.metric("Z-Score", f"{z_score:.2f}" if z_score else "N/A", help=z_msg)
            
            # 詳細理由
            st.markdown("#### 📝 評分依據")
            for r in reasons: st.write(r)

            # K線圖
            if not price_df.empty:
                st.plotly_chart(go.Figure(data=[go.Candlestick(x=price_df.index, open=price_df['Open'], high=price_df['High'], low=price_df['Low'], close=price_df['Close'])]), use_container_width=True)

        except Exception as e:
            st.error(f"分析失敗: {e}")
