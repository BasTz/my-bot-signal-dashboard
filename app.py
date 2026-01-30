import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import altair as alt
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
@st.cache_data(ttl=60)
def fetch_data():
    # 1. Fetch Symbol History
    history_url = f"{API_BASE_URL}/pnl/history"
    history_data = []
    try:
        response = requests.get(history_url, timeout=5)
        response.raise_for_status()
        history_data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from {history_url}: {e}")

    # 2. Fetch Global History
    global_url = f"{API_BASE_URL}/pnl/global-history"
    global_data = []
    try:
        response = requests.get(global_url, timeout=5)
        response.raise_for_status()
        global_data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from {global_url}: {e}")

    return history_data, global_data

# Function to fetch YTD data (separate cache to allow year change)
@st.cache_data(ttl=300)
def fetch_ytd_data(year):
    ytd_url = f"{API_BASE_URL}/pnl/ytd-history?year={year}"
    try:
        response = requests.get(ytd_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Don't show error immediately to avoid clutter if year is not found
        return []

import datetime

# Sidebar Configuration
st.sidebar.header("Configuration")
current_year = datetime.datetime.now().year
selected_year = st.sidebar.number_input("Select Year", min_value=2023, max_value=current_year + 1, value=current_year)
st.sidebar.divider()
auto_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=False)
refresh_interval = st.sidebar.number_input("Refresh Interval (seconds)", min_value=10, value=60)

history_data, global_data = fetch_data()
ytd_data = fetch_ytd_data(selected_year)

# 4. แสดงผลข้อมูล
if history_data or global_data or ytd_data:
    # 4.0 YTD History (New Section)
    if ytd_data:
        st.subheader(f"YTD Performance ({selected_year})")
        ytd_df = pd.DataFrame(ytd_data)
        if 'date' in ytd_df.columns:
            ytd_df['date'] = pd.to_datetime(ytd_df['date'])
            
            # Create tabs for Cumulative PNL and Daily Income
            tab1, tab2 = st.tabs(["Cumulative PNL", "Daily Income"])
            
            with tab1:
                # Altair Chart for Cumulative PNL
                chart_cum = alt.Chart(ytd_df).mark_line(color="#29b5e8").encode(
                    x=alt.X('date:T', axis=alt.Axis(format='%d/%m', title='Date', labelAngle=0)),
                    y=alt.Y('cumulative_pnl:Q', title='Cumulative PNL (USD)'),
                    tooltip=[
                        alt.Tooltip('date', title='Date', format='%d/%m/%Y'),
                        alt.Tooltip('cumulative_pnl', title='Cum. PNL', format=',.4f')
                    ]
                )
                st.altair_chart(chart_cum, use_container_width=True)
                
                # Show latest cumulative PNL
                latest_cum_pnl = ytd_df.iloc[-1]['cumulative_pnl'] if not ytd_df.empty else 0
                st.metric(f"Total Cumulative PNL ({selected_year})", f"{latest_cum_pnl:,.4f} USD")

            with tab2:
                # Altair Chart for Daily Income (with color coding)
                chart_income = alt.Chart(ytd_df).mark_bar().encode(
                    x=alt.X('date:T', axis=alt.Axis(format='%d/%m', title='Date', labelAngle=0)),
                    y=alt.Y('income:Q', title='Daily Income (USD)'),
                    color=alt.condition(
                        alt.datum.income >= 0,
                        alt.value("#2ecc71"),  # Green
                        alt.value("#e74c3c")   # Red
                    ),
                    tooltip=[
                        alt.Tooltip('date', title='Date', format='%d/%m/%Y'),
                        alt.Tooltip('income', title='Income', format=',.4f')
                    ]
                )
                st.altair_chart(chart_income, use_container_width=True)

    # 4.1 Global Data Processing (Total PNL)
    current_total_upnl = 0.0
    
    if global_data:
        global_df = pd.DataFrame(global_data)
        if 'ts' in global_df.columns:
            global_df['datetime'] = pd.to_datetime(global_df['ts'], unit='s')
            
        if 'upnl' in global_df.columns:
             # หาค่าล่าสุดสำหรับ Metric
             if not global_df.empty:
                # เรียงตามเวลาเพื่อให้แน่ใจว่าได้ตัวล่าสุด
                latest_global = global_df.sort_values('ts').iloc[-1]
                current_total_upnl = latest_global['upnl']
                
             st.subheader("15m Total Unrealized PNL")
             st.line_chart(global_df.set_index('datetime')['upnl'])

    # 4.2 Symbol Data Processing
    active_symbols_count = 0
    last_update_str = "-"
    
    if history_data:
        df = pd.DataFrame(history_data)
        
        if 'ts' in df.columns:
            df['datetime'] = pd.to_datetime(df['ts'], unit='s')
            last_update_str = df['datetime'].max().strftime('%H:%M:%S')
            
            # Pivot for chart
            chart_df = df.pivot(index='datetime', columns='symbol', values='upnl')
            
            # Count active symbols (from latest timestamp)
            latest_ts = df['ts'].max()
            active_symbols_count = len(df[df['ts'] == latest_ts])

            st.subheader("uPNL History per Symbol")
            st.line_chart(chart_df)

            # Bar Chart for Latest UPNL
            st.subheader("Current uPNL by Symbol")
            latest_data_df = df[df['ts'] == latest_ts].set_index('symbol')['upnl'].sort_values()
            
            # Color coding (Optional: Streamlit bar chart is simple, but we can separate + and - if needed, 
            # here we just show the standard bar chart first)
            st.bar_chart(latest_data_df)
            
            with st.expander("Show Raw Symbol Data"):
                st.dataframe(df.sort_values(by='datetime', ascending=False), use_container_width=True)

    # 4.3 KPI Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Unrealized PNL", f"{current_total_upnl:,.2f} USD")
    col2.metric("Last Update", last_update_str)
    col3.metric("Active Symbols", active_symbols_count)

else:
    st.info("No data available from API.")

# 5. แสดงสถานะ connection
col1, col2 = st.columns(2)
status_color = "normal" if (history_data or global_data) else "off"
col1.markdown("API Status", "Connected" if (history_data or global_data) else "Disconnected")
# col2.metric("API URL", API_BASE_URL)

# 6. ปุ่ม Refresh
if st.button('🔄 Refresh Data'):
    st.cache_data.clear()
    st.rerun()

if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
