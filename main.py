import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import DataEngine
from src.metrics import MetricCalculator
from src.strategy import generate_signals, suggest_order_type

st.set_page_config(page_title="台股全方位量化系統", layout="wide")
st.title("🇹🇼 台股在地化全方位決策系統")
st.markdown("### 整合融資籌碼、NCAV 與大師分類模型 (防呆修復版)")

with st.sidebar:
    st.header("系統設定")
    stock_id = st.text_input("股票代號", value="2330", help="輸入代號，如 2330")
    
    if "FINMIND_TOKEN" in st.secrets:
        token = st.secrets["FINMIND_TOKEN"]
        st.success("✅ Token 已載入")
    else:
        token = st.text_input("FinMind Token", type="password")
    
    run_btn = st.button("執行全方位分析", type="primary")
    
    st.divider()
    show_debug = st.checkbox("🔧 顯示原始數據狀態 (除錯用)")

if run_btn:
    engine = DataEngine(token=token if token else None)
    
    with st.spinner(f"正在分析 {stock_id} (籌碼/財報/營收)..."):
        try:
            # 1. 獲取數據
            price_df, info = engine.get_price_data(stock_id)
            bs, inc, cf, rev, div, chip, margin = engine.get_financial_data(stock_id)
            
            # --- 除錯模式顯示 ---
           # main.py 的一部分，請替換 if show_debug: 這一塊

            # --- 除錯模式顯示 ---
            if show_debug:
                with st.expander("🔍 原始數據檢查 (Debug)"):
                    st.write("--- 籌碼數據 (Chip) ---")
                    if not chip.empty: 
                        st.write(f"資料筆數: {len(chip)}")
                        st.write(f"欄位名稱: {list(chip.columns)}") # 秀出欄位名
                        st.dataframe(chip.tail(5)) # 秀出最近5筆
                    else: 
                        st.error("⚠️ 籌碼資料 (Chip) 為空！")
                    
                    st.write("--- 融資數據 (Margin) ---")
                    if not margin.empty:
                        st.write(f"欄位名稱: {list(margin.columns)}")
                        st.dataframe(margin.tail(5))
            
            # 2. 計算指標
            calculator = MetricCalculator(bs, inc, cf, rev, div, chip, margin, info)
            
            f_score, f_details = calculator.calculate_f_score()
            z_score, z_msg = calculator.calculate_z_score()
            mom, yoy = calculator.calculate_revenue_growth()
            guru_metrics = calculator.calculate_guru_metrics()
            chip_metrics = calculator.calculate_chip_metrics()
            margin_metrics = calculator.calculate_margin_metrics()
            
            # 3. 策略生成
            total_score, action, color, reasons = generate_signals(
                f_score, z_score, info, mom, yoy, guru_metrics, chip_metrics, margin_metrics
            )
            
            # --- UI ---
            st.divider()
            
            # A. 核心決策
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"決策評級: :{color}[{action}] (總分 {total_score})")
                st.caption(f"股票分類: {guru_metrics.get('Lynch Category', '未分類')}")
                if "Buy" in action: st.info(suggest_order_type(action))
            with c2:
                graham = guru_metrics.get('Graham Number', 0)
                ncav = guru_metrics.get('NCAV', 0)
                price = info.get('currentPrice', info.get('regularMarketPreviousClose', 0))
                
                if ncav > 0:
                    st.metric("NCAV (清算價值)", f"{ncav:.1f}", delta=f"現價 {price}", delta_color="off")
                else:
                    st.metric("葛拉漢估值", f"{graham:.1f}", delta=f"{((price-graham)/graham)*100:.1f}%" if graham else None, delta_color="inverse")

            st.divider()
            
            # B. 籌碼與融資 (儀表板)
            st.subheader("📊 籌碼與散戶指標")
            m1, m2, m3, m4 = st.columns(4)
            
            f_net = chip_metrics.get("Foreign Net (3d)", 0) / 1000
            m1.metric("外資 (3日)", f"{int(f_net)} 張", delta="連買" if chip_metrics.get("Foreign Consecutive") else "無連買")
            
            t_net = chip_metrics.get("Trust Net (10d)", 0) / 1000
            delta_t = "🔥 認養中" if chip_metrics.get("Trust Active Buy") else ("大股本" if not chip_metrics.get("Is Small Cap") else "無佈局")
            m2.metric("投信 (10日)", f"{int(t_net)} 張", delta=delta_t)
            
            m_bal = margin_metrics.get("Latest Balance", 0) / 1000
            m_chg = margin_metrics.get("Change", 0) / 1000
            m3.metric("融資餘額", f"{int(m_bal)} 張", delta=f"{int(m_chg)} 張 (近5日)", delta_color="inverse")
            
            m4.metric("營收 YoY", f"{yoy:.1f}%" if yoy else "N/A", delta_color="normal")

            # C. 大師指標
            st.subheader("🎓 華爾街大師指標")
            g1, g2, g3 = st.columns(3)
            peg = guru_metrics.get('Lynch PEG')
            g1.metric("林區 PEG", f"{peg:.2f}" if peg is not None else "N/A", help="< 1.0 合理")
            g2.metric("神奇公式", f"ROC {guru_metrics.get('Magic ROC', 0):.1f}%")
            g3.metric("F-Score", f"{f_score}/9")

            st.markdown("#### 📝 評分依據")
            for r in reasons: st.write(r)

            if not price_df.empty:
                st.plotly_chart(go.Figure(data=[go.Candlestick(x=price_df.index, open=price_df['Open'], high=price_df['High'], low=price_df['Low'], close=price_df['Close'])]), use_container_width=True)

        except Exception as e:
            st.error(f"分析失敗: {e}")
