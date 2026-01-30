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
st.title("📈 Crypto Signal Dashboard")
st.caption("ข้อมูล Real-time จาก Bot")

# Configuration: URL สำหรับ API (รองรับการเปลี่ยนเป็น Cloud URL ผ่าน st.secrets หรือ Environment Variable)
try:
    # ลองดึงจาก st.secrets ก่อน (สำหรับการ Deploy บน streamlit.io)
    API_BASE_URL = st.secrets["API_BASE_URL"]
except (FileNotFoundError, KeyError):
    # ถ้าไม่มี ให้ใช้ค่า Default หรือจาก Environment Variable
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# Configuration: API Key Authentication
try:
    API_ACCESS_KEY = st.secrets["API_ACCESS_KEY"]
except (FileNotFoundError, KeyError):
    API_ACCESS_KEY = os.environ.get("API_ACCESS_KEY", "mysecretkey")

def get_headers():
    return {"X-API-Key": API_ACCESS_KEY}

# 3. ดึงข้อมูลจาก API
@st.cache_data(ttl=60)
def fetch_data():
    headers = get_headers()
    # 1. Fetch Symbol History
    history_url = f"{API_BASE_URL}/pnl/history"
    history_data = []
    try:
        response = requests.get(history_url, headers=headers, timeout=5)
        response.raise_for_status()
        history_data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from {history_url}: {e}")

    # 2. Fetch Global History
    global_url = f"{API_BASE_URL}/pnl/global-history"
    global_data = []
    try:
        response = requests.get(global_url, headers=headers, timeout=5)
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
        response = requests.get(ytd_url, headers=get_headers(), timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        # Don't show error immediately to avoid clutter if year is not found
        return []

# Function to fetch Open Positions (Real-time)
@st.cache_data(ttl=15) # Cache shorter for real-time positions
def fetch_open_positions():
    url = f"{API_BASE_URL}/position/open"
    headers = get_headers()
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
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
position_data = fetch_open_positions()

# 4. แสดงผลข้อมูล
if history_data or global_data or ytd_data or position_data:
    # 4.0 YTD History (New Section)
    latest_cum_pnl = 0.0
    if ytd_data and isinstance(ytd_data, list):
         ytd_df = pd.DataFrame(ytd_data)
         if not ytd_df.empty and 'cumulative_pnl' in ytd_df.columns:
             latest_cum_pnl = ytd_df.iloc[-1]['cumulative_pnl']

         st.subheader(f"YTD Performance ({selected_year}) | Total: {latest_cum_pnl:,.4f} USD")
         
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
    report_msg = ""
    
    if global_data:
        global_df = pd.DataFrame(global_data)
        if 'ts' in global_df.columns:
            global_df['datetime'] = pd.to_datetime(global_df['ts'], unit='s')
            
        if 'upnl' in global_df.columns:
             # หาค่าล่าสุดสำหรับ Metric
             if not global_df.empty:
                # เรียงตามเวลาเพื่อให้แน่ใจว่าได้ตัวล่าสุด
                global_df = global_df.sort_values('ts')
                latest_global = global_df.iloc[-1]
                current_total_upnl = latest_global['upnl']
                
                # --- Calculate 15Min Change ---
                diff = 0.0
                try:
                    # หาข้อมูลเมื่อ 15 นาทีที่แล้ว (900 วินาที)
                    target_ts = latest_global['ts'] - 900
                    # หา index ของข้อมูลที่ใกล้เคียงที่สุด
                    idx = (global_df['ts'] - target_ts).abs().idxmin()
                    past_val = global_df.loc[idx]['upnl']
                    diff = current_total_upnl - past_val
                except Exception:
                    diff = 0.0 # กรณีข้อมูลไม่พอ
                    
                # --- Prepare Report Variables ---
                emoji_total = "🟢" if current_total_upnl >= 0 else "🔴"
                upnl_sign = "+" if current_total_upnl >= 0 else ""
                
                diff_icon = "🟢" if diff >= 0 else "🔴"
                diff_sign = "+" if diff >= 0 else ""
                diff_str = f"\n📉 *15Min Change*: {diff_icon} `{diff_sign}{diff:.2f} USD`"
                
                realized_pnl = 0.0
                ytd_pnl = 0.0
                
                # Try to get Realized PNL from YTD Data
                if ytd_data and isinstance(ytd_data, list):
                     ytd_df_rep = pd.DataFrame(ytd_data)
                     if not ytd_df_rep.empty:
                         # Assume last entry is today
                         last_ytd = ytd_df_rep.iloc[-1]
                         realized_pnl = last_ytd.get('income', 0.0)
                         ytd_pnl = last_ytd.get('cumulative_pnl', 0.0)

                realized_icon = "💰" if realized_pnl >= 0 else "💸"
                realized_sign = "+" if realized_pnl >= 0 else ""
                
                ytd_icon = "📈" if ytd_pnl >= 0 else "📉"
                ytd_sign = "+" if ytd_pnl >= 0 else ""

                # --- Build Message for Copying (Telegram Markdown) ---
                copy_msg = f"*Total uPNL*: {emoji_total} `{current_total_upnl:+.2f} USD`\n"
                copy_msg += f"*15m Change*: `{diff:+.2f} USD`\n"
                copy_msg += f"--------------------------------\n"
                
                # --- Build HTML for Display (Colorful UI) ---
                html_report = f"""
                <div style="background-color:#1E1E1E; padding:15px; border-radius:10px; border:1px solid #333;">
                    <h3 style="margin-top:0; color:white;">💰 Total uPNL: <span style="color:{'#2ecc71' if current_total_upnl >= 0 else '#e74c3c'};">{current_total_upnl:+.2f} USD</span></h3>
                    <p style="color:#aaa; margin-bottom:5px;">📉 15m Change: <span style="color:{'#2ecc71' if diff >= 0 else '#e74c3c'};">{diff:+.2f} USD</span></p>
                    <p style="color:#aaa; margin-bottom:5px;">💰 Day Realized: <span style="color:{'#2ecc71' if realized_pnl >= 0 else '#e74c3c'};">{realized_pnl:+.2f} USD</span></p>
                    <p style="color:#aaa; margin-bottom:15px;">📈 YTD Realized: <span style="color:{'#2ecc71' if ytd_pnl >= 0 else '#e74c3c'};">{ytd_pnl:+.2f} USD</span></p>
                    <hr style="border-top: 1px solid #444;">
                    <table style="width:100%; color:white;">
                """

                # Add Symbol Breakdown
                is_using_live_pos = False

                positions_to_process = []
                if position_data and isinstance(position_data, list):
                     is_using_live_pos = True
                     positions_to_process = position_data
                elif history_data:
                     # Convert history to list of dicts for unified processing
                     hist_df = pd.DataFrame(history_data)
                     latest_ts = hist_df['ts'].max()
                     current_syms = hist_df[hist_df['ts'] == latest_ts].sort_values('upnl', ascending=False)
                     positions_to_process = current_syms.to_dict('records')

                for pos in positions_to_process:
                    # Generic key access
                    sym = pos.get('Symbol', pos.get('symbol', 'Unknown'))
                    upnl = float(pos.get('uPNL', pos.get('upnl', 0.0)))
                    side = pos.get('Side', pos.get('side', '-'))
                    if not isinstance(side, str): side = '-'
                    side = side.upper()

                    # Colors
                    side_color = "#2ecc71" if side == "LONG" else "#e74c3c" if side == "SHORT" else "#aaa"
                    pnl_color = "#2ecc71" if upnl >= 0 else "#e74c3c"
                    
                    # Add to HTML
                    html_report += f"<tr><td style='font-weight:bold; color:#3498db; width:30%;'>{sym}</td>"
                    html_report += f"<td style='font-weight:bold; color:{side_color}; width:30%;'>{side}</td>"
                    html_report += f"<td style='text-align:right; font-family:monospace; color:{pnl_color};'>{upnl:+.2f} $</td></tr>"

                    
                    # Add to Copy Msg
                    icon = "🟢" if upnl >= 0 else "🔴"
                    copy_msg += f"`{sym:<6} | {side:<5}` {icon} `{upnl:+.2f} $`\n"

                html_report += "</table></div>"

                # Show Colorful Report
                st.markdown(html_report, unsafe_allow_html=True)


             
             st.subheader("15m Total Unrealized PNL")
             # Altair Chart for Global PNL (Locked)
             chart_global = alt.Chart(global_df).mark_line().encode(
                 x=alt.X('datetime:T', title='Time', axis=alt.Axis(format='%H:%M')),
                 y=alt.Y('upnl:Q', title='uPNL (USD)'),
                 tooltip=[
                     alt.Tooltip('datetime', title='Time', format='%H:%M:%S'),
                     alt.Tooltip('upnl', title='uPNL', format=',.2f')
                 ]
             )
             st.altair_chart(chart_global, use_container_width=True)

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
            # Altair Chart for Symbol History (Locked)
            chart_symbols = alt.Chart(df).mark_line().encode(
                x=alt.X('datetime:T', title='Time', axis=alt.Axis(format='%H:%M')),
                y=alt.Y('upnl:Q', title='uPNL (USD)'),
                color=alt.Color('symbol:N', title='Symbol'),
                tooltip=[
                    alt.Tooltip('datetime', title='Time', format='%H:%M:%S'),
                    'symbol',
                    alt.Tooltip('upnl', title='uPNL', format=',.2f')
                ]
            )
            st.altair_chart(chart_symbols, use_container_width=True)

            # Bar Chart for Latest UPNL
            st.subheader("Current uPNL by Symbol")
            
            # Use Position Data for Bar Chart if available (More accurate)
            if position_data and isinstance(position_data, list):
                 pos_df = pd.DataFrame(position_data)
                 # Normalize column names
                 if 'uPNL' in pos_df.columns: pos_df['upnl'] = pos_df['uPNL']
                 if 'Symbol' in pos_df.columns: pos_df['symbol'] = pos_df['Symbol']

                 pos_df['label'] = pos_df.apply(lambda x: f"{x['symbol']}\n{x['upnl']:.2f}", axis=1)

                 base = alt.Chart(pos_df).encode(
                    x=alt.X('label:N', axis=alt.Axis(title='', labelAngle=0), sort=alt.EncodingSortField(field="upnl", order="ascending")),
                    y=alt.Y('upnl:Q', title='uPNL (USD)'),
                    tooltip=['Symbol', 'uPNL', 'Side']
                 )

                 chart_upnl = base.mark_bar().encode(
                    color=alt.condition(
                        alt.datum.upnl >= 0,
                        alt.value("#2ecc71"),  # Green
                        alt.value("#e74c3c")   # Red
                    )
                 ) + base.mark_text(dy= -5 if pos_df['upnl'].max() < 0 else 5).encode(
                     text=alt.Text('upnl:Q', format='.2f')
                 )
                 st.altair_chart(chart_upnl, use_container_width=True)
                 
                 with st.expander("Show Raw Position Data"):
                     st.dataframe(pos_df, use_container_width=True)

            elif not df.empty:
                # Altair Bar Chart for Latest UPNL with Custom Labels (Fallback)
                latest_df = df[df['ts'] == latest_ts].copy()
                latest_df['label'] = latest_df.apply(lambda x: f"{x['symbol']}\n{x['upnl']:.2f}", axis=1)

                base = alt.Chart(latest_df).encode(
                    x=alt.X('label:N', axis=alt.Axis(title='', labelAngle=0), sort=alt.EncodingSortField(field="upnl", order="ascending")),
                    y=alt.Y('upnl:Q', title='uPNL (USD)'),
                    tooltip=['symbol', 'upnl', 'datetime']
                )

                chart_upnl = base.mark_bar().encode(
                    color=alt.condition(
                        alt.datum.upnl >= 0,
                        alt.value("#2ecc71"),  # Green
                        alt.value("#e74c3c")   # Red
                    )
                ) + base.mark_text(dy= -5 if latest_df['upnl'].max() < 0 else 5).encode(
                     text=alt.Text('upnl:Q', format='.2f')
                )
                
                st.altair_chart(chart_upnl, use_container_width=True)
                
                with st.expander("Show Raw Symbol Data"):
                    st.dataframe(df.sort_values(by='datetime', ascending=False), use_container_width=True)

    # 4.3 KPI Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("15m Unrealized PNL", f"{current_total_upnl:,.2f} USD")
    col2.metric("Last Update", last_update_str)
    col3.metric("Active Symbols", active_symbols_count)

else:
    st.info("No data available from API.")

# 5. แสดงสถานะ connection
st.divider()
status_text = "🟢 Connected" if (history_data or global_data) else "🔴 Disconnected"
st.caption(f"API Status: {status_text}")

# 6. ปุ่ม Refresh
if st.button('🔄 Refresh Data'):
    st.cache_data.clear()
    st.rerun()

if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
