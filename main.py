import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

# 1. 頁面設定
st.set_page_config(page_title="台股量化系統 (研究報告實作版)", layout="wide")
st.title("📈 台股量化決策系統")
st.markdown("### 嚴格執行「台股量化交易系統研究報告」之邏輯")

# 2. 側邊欄與 Token 安全邏輯
with st.sidebar:
    st.header("系統設定")
    stock_id = st.text_input("股票代號", value="2330", help="輸入台股代號，如 2330 或 2603")
    
    # --- Token 安全讀取邏輯 ---
    # 優先從 Streamlit Secrets 讀取，避免將密碼暴露在程式碼中
    if "FINMIND_TOKEN" in st.secrets:
        token = st.secrets["FINMIND_TOKEN"]
        st.success("✅ 已自動載入 API Token")
    else:
        # 本地端或未設定 Secrets 時顯示輸入框
        token = st.text_input("FinMind API Token", type="password", help="建議在 Streamlit 後台設定 Secrets 以免重複輸入")
    # -----------------------

    run_btn = st.button("執行報告邏輯分析", type="primary")

# 3. 主執行邏輯
if run_btn:
    # 初始化數據引擎
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在依照報告邏輯分析 {stock_id} ..."):
        try:
            # A. 數據層 (Data Layer)
            # 獲取股價與詳細資料
            price_df, info = engine.get_price_data(stock_id)
            # 獲取四大報表 (含月營收 rev)
            bs, inc, cf, rev = engine.get_financial_data(stock_id)
            
            # 基本檢核
            if bs.empty or inc.empty:
                st.error("❌ 數據不足，無法進行報告模型分析 (可能為新上市股或 FinMind 資料缺漏)。")
                st.stop()
            
            # B. 指標層 (Metric Layer)
            # 將月營收 (rev) 傳入計算器
            calculator = MetricCalculator(bs, inc, cf, rev, info)
            
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            # 計算報告 2.3.1 強調的營收動能
            mom, yoy = calculator.calculate_revenue_growth()
            
            # C. 策略層 (Strategy Layer)
            # 傳入所有參數進行表 2 的評分
            total_score, action, color, reasons = generate_signals(f_score, z_score, info, mom, yoy)
            
            # --- 儀表板顯示 (UI) ---
            st.divider()
            
            # 第一列：核心指標
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("F-Score", f"{f_score}/9", help="皮爾托斯基分數 (基本面體質)")
            c2.metric("Z-Score", f"{z_score:.2f}" if z_score is not None else "N/A", help=f"破產風險: {z_msg}")
            
            # 顯示營收數據 (報告強調的高頻指標)
            yoy_display = f"{yoy:.1f}%" if yoy is not None else "N/A"
            mom_display = f"{mom:.1f}%" if mom is not None else "N/A"
            c3.metric("營收年增 (YoY)", yoy_display, delta_color="normal")
            c4.metric("營收月增 (MoM)", mom_display, delta_color="normal")
            
            st.markdown("---")
            
            # 第二列：最終決策與下單建議
            st.subheader(f"研究報告決策: :{color}[{action}] (總分 {total_score})")
            
            # 若為買進/持有，顯示延遲對策建議 (報告第五章)
            if "Buy" in action or "Hold" in action:
                st.info(suggest_order_type(action), icon="🛡️")
            
            # 第三列：詳細理由
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.write("**📝 評分依據 (表 2 估值模型):**")
                for r in reasons:
                    st.write(r)
            with col_r:
                st.write("**🔍 F-Score 細項分析:**")
                for d in f_details:
                    st.write(d)

            # 第四列：技術面 K 線圖
            if not price_df.empty:
                st.markdown("#### 股價走勢圖")
                fig = go.Figure(data=[go.Candlestick(x=price_df.index,
                                open=price_df['Open'], high=price_df['High'],
                                low=price_df['Low'], close=price_df['Close'])])
                fig.update_layout(xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"分析過程發生中斷: {str(e)}")
            st.markdown("建議檢查：1. 股票代號是否正確 2. 該公司是否暫停交易或資料異常")
