import streamlit as st
import pandas as pd
import numpy as np

# 1. ตั้งค่าหน้าเว็บให้ดูบนมือถือสวยๆ
st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")

# 2. หัวข้อ
st.title("📈 Bitcoin Signal Dashboard")
st.caption("ข้อมูล Real-time จาก Bot")

# 3. จำลองข้อมูลกราฟ (Mock Data)
# ของจริงตรงนี้คุณจะดึงจาก Database หรือ API
chart_data = pd.DataFrame(
    np.random.randn(20, 3),
    columns=['BTC', 'ETH', 'SOL']
)

# 4. แสดงกราฟ (Line Chart)
st.line_chart(chart_data)

# 5. แสดงสถานะล่าสุด (Metric)
col1, col2 = st.columns(2)
col1.metric("BTC Price", "42,000 USD", "1.2%")
col2.metric("Signal", "BUY", "Strong")

# 6. ปุ่ม Refresh
if st.button('🔄 Refresh Data'):
    st.rerun()
