# main.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

st.set_page_config(page_title="台股量化系統 (研究報告實作版)", layout="wide")
st.title("📈 台股量化決策系統")
st.markdown("### 嚴格執行「台股量化交易系統研究報告」之邏輯")

# --- Sidebar ---
with st.sidebar:
    st.header("參數設定")
    stock_id = st.text_input("股票代號", value="2330")
    token = st.text_input("FinMind API Token", type="password")
    run_btn = st.button("執行報告邏輯分析", type="primary")

# --- Main ---
if run_btn:
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在依照報告邏輯分析 {stock_id} ..."):
        try:
            # 1. 獲取數據
            price_df, info = engine.get_price_data(stock_id)
            bs, inc, cf, rev = engine.get_financial_data(stock_id)
            
            if bs.empty or inc.empty:
                st.error("❌ 數據不足，無法進行報告模型分析。")
                st.stop()
            
            # 2. 計算指標 (加入 rev 參數)
            # 注意：這裡把 rev 傳進去了
            calculator = MetricCalculator(bs, inc, cf, rev, info)
            
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            # 新增：計算營收成長
            mom, yoy = calculator.calculate_revenue_growth()
            
            # 3. 生成策略 (依照表 2)
            total_score, action, color, reasons = generate_signals(f_score, z_score, info, mom, yoy)
            
            # --- 顯示結果 ---
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("F-Score", f"{f_score}/9")
            c2.metric("Z-Score", f"{z_score:.2f}" if z_score else "N/A")
            # 顯示營收數據
            c3.metric("營收 YoY", f"{yoy:.1f}%" if yoy else "N/A", delta_color="normal")
            c4.metric("營收 MoM", f"{mom:.1f}%" if mom else "N/A", delta_color="normal")
            
            st.markdown("---")
            st.subheader(f"研究報告決策: :{color}[{action}] (總分 {total_score})")
            
            if "Buy" in action or "Hold" in action:
                st.info(suggest_order_type(action))
            
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.write("**📝 評分依據 (表 2):**")
                for r in reasons:
                    st.write(r)
            with col_r:
                st.write("**🔍 F-Score 細項:**")
                for d in f_details:
                    st.write(d)

            # K線圖
            if not price_df.empty:
                st.plotly_chart(go.Figure(data=[go.Candlestick(x=price_df.index, open=price_df['Open'], high=price_df['High'], low=price_df['Low'], close=price_df['Close'])]), use_container_width=True)

        except Exception as e:
            st.error(f"分析中斷: {e}")
