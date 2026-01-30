import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import time

# 1. ตั้งค่าหน้าเว็บให้ดูบนมือถือสวยๆ
st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")

# 2. หัวข้อ
st.title("📈 Bitcoin Signal Dashboard")
st.caption("ข้อมูล Real-time จาก Bot")

# Configuration: URL สำหรับ API (รองรับการเปลี่ยนเป็น Cloud URL ผ่าน st.secrets หรือ Environment Variable)
try:
    # ลองดึงจาก st.secrets ก่อน (สำหรับการ Deploy บน streamlit.io)
    API_BASE_URL = st.secrets["API_BASE_URL"]
except (FileNotFoundError, KeyError):
    # ถ้าไม่มี ให้ใช้ค่า Default หรือจาก Environment Variable
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# 3. ดึงข้อมูลจาก API
@st.cache_data(ttl=60)  # Cache ข้อมูล 60 วินาที
def fetch_data():
    url = f"{API_BASE_URL}/pnl/history"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from {url}: {e}")
        return []

data = fetch_data()

# 4. แสดงผลข้อมูล
if data:
    df = pd.DataFrame(data)
    
    # 4.1 แปลง Timestamp เป็น Datetime
    if 'ts' in df.columns:
        df['datetime'] = pd.to_datetime(df['ts'], unit='s')
        
    # 4.2 เตรียมข้อมูลสำหรับกราฟแยกตาม Symbol
    # Pivot Table: index=datetime, columns=symbol, values=upnl
    chart_df = df.pivot(index='datetime', columns='symbol', values='upnl')
    
    # 4.3 เตรียมข้อมูลสำหรับกราฟรวม (Total PNL)
    # รวม PNL ของทุกเหรียญในแต่ละช่วงเวลา
    total_pnl_df = df.groupby('datetime')['upnl'].sum()

    # แสดง KPI Cards ล่าสุด
    latest_ts = df['ts'].max()
    latest_data = df[df['ts'] == latest_ts]
    total_upnl = latest_data['upnl'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Unrealized PNL", f"{total_upnl:,.2f} USD")
    col2.metric("Last Update", pd.to_datetime(latest_ts, unit='s').strftime('%H:%M:%S'))
    col3.metric("Active Symbols", len(latest_data))

    st.subheader("Total Portfolio PNL")
    st.line_chart(total_pnl_df)
    
    st.subheader("PNL per Symbol")
    st.line_chart(chart_df)
    
    # แสดงข้อมูลตารางดิบ (Optional)
    with st.expander("Show Raw Data"):
        st.dataframe(df.sort_values(by='datetime', ascending=False), use_container_width=True)
else:
    st.info("No data available or failed to connect to API.")

# 5. แสดงสถานะ connection
col1, col2 = st.columns(2)
status_color = "normal" if data else "off"
col1.metric("API Status", "Connected" if data else "Disconnected")
col2.metric("API URL", API_BASE_URL)

# 6. ปุ่ม Refresh
if st.button('🔄 Refresh Data'):
    st.cache_data.clear()
    st.rerun()

# 7. Auto Refresh Logic
st.sidebar.header("Configuration")
auto_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=False)
refresh_interval = st.sidebar.number_input("Refresh Interval (seconds)", min_value=10, value=60)

if auto_refresh:
    # รอเวลาแล้วค่อย Refresh
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
