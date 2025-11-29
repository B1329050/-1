# main.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

# 頁面基本設定
st.set_page_config(page_title="台股量化系統 Pro", layout="wide")

st.title("📈 台股量化交易決策系統 (TW-Quant Pro)")
st.markdown("### 華爾街指標在地化實踐版")

# --- 側邊欄 ---
with st.sidebar:
    st.header("系統設定")
    stock_id = st.text_input("股票代號", value="2330", help="輸入台股代號，如 2330")
    token = st.text_input("FinMind API Token", type="password", help="建議輸入 Token 以解除流量限制")
    st.markdown("---")
    st.caption("無 Token 模式下，每次請求將強制間隔 3 秒。")
    run_btn = st.button("🚀 執行深度分析", type="primary")

# --- 主邏輯 ---
if run_btn:
    # 1. 初始化數據引擎
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在分析 {stock_id} ... (請稍候，數據拉取中)"):
        try:
            # A. 數據層 (Data Layer)
            price_df, info = engine.get_price_data(stock_id)
            bs, inc, cf, rev = engine.get_financial_data(stock_id)
            
            # 檢查是否成功獲取財報
            if bs.empty or inc.empty:
                st.error("❌ FinMind 查無財務數據，請確認代號是否正確，或是否為剛上市之新股。")
                st.stop()
            
            # B. 指標層 (Metric Layer)
            calculator = MetricCalculator(bs, inc, cf, info)
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            
            # C. 策略層 (Strategy Layer)
            total_score, action, color, reasons = generate_signals(f_score, z_score, info, f_details)
            
            # --- 儀表板顯示 (UI) ---
            
            # 1. 頂部關鍵指標
            st.divider()
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                st.metric("Piotroski F-Score", f"{f_score} / 9")
            with col2:
                z_display = f"{z_score:.2f}" if z_score is not None else "N/A"
                st.metric("Altman Z-Score", z_display, delta_color="normal", help=z_msg)
            with col3:
                st.subheader(f"評級: :{color}[{action}]")
                st.metric("綜合總分", total_score, help="基於估值加扣分模型")

            # 2. 延遲對策建議
            if "Buy" in action:
                st.info(suggest_order_type(action), icon="🛡️")

            # 3. 詳細分析 Tab
            tab1, tab2, tab3 = st.tabs(["📊 技術面 K 線", "📝 F-Score 詳細報告", "📑 原始財報數據"])
            
            with tab1:
                if not price_df.empty:
                    fig = go.Figure(data=[go.Candlestick(x=price_df.index,
                                    open=price_df['Open'], high=price_df['High'],
                                    low=price_df['Low'], close=price_df['Close'])])
                    fig.update_layout(title=f"{stock_id} 日線圖", xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("無法獲取股價數據")
            
            with tab2:
                st.write(f"**F-Score 得分細項 ({len(f_details)} 項):**")
                for item in f_details:
                    st.write(item)
                
                st.divider()
                st.write("**估值與風險加扣分原因:**")
                for reason in reasons:
                    st.write(f"- {reason}")
                
            with tab3:
                st.markdown("#### 綜合損益表 (部分)")
                st.dataframe(inc.head(5))
                st.markdown("#### 資產負債表 (部分)")
                st.dataframe(bs.head(5))

        except Exception as e:
            st.error(f"系統執行發生未預期的錯誤: {str(e)}")
            st.markdown("建議檢查：API 連線狀態或該股票是否有特殊交易變更。")
