import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="FINEDA HQ", layout="wide", page_icon="📈")

# --- 1. AUTHENTICATION ---
if "password_correct" not in st.session_state:
    st.title("🛡️ FineData HQ Login")
    pwd = st.text_input("Admin Password", type="password")
    if st.button("Access"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Access Denied")
    st.stop()

# --- 2. DATA CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0).astype(str)

# Ensure columns exist for links
for col in ['Image_front', 'Image_back', 'Order_ID']:
    if col not in df.columns:
        df[col] = "None"

# --- 3. NAVIGATION ---
page = st.sidebar.radio("Navigation", ["📊 Dashboard", "📜 Order Logs", "🎨 Design Vault"])

# --- PAGE: ORDER LOGS ---
if page == "📜 Order Logs":
    st.header("Order Management")
    search = st.text_input("🔍 Search Orders")
    filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    
    st.divider()
    order_id = st.selectbox("Quick View Design", ["Select..."] + list(df['Order_ID'].unique()))
    if order_id != "Select...":
        row = df[df['Order_ID'] == order_id].iloc[0]
        v1, v2 = st.columns(2)
        if row['Image_front'] != "None": v1.link_button("👁️ Front Design", row['Image_front'])
        if row['Image_back'] != "None": v2.link_button("👁️ Back Design", row['Image_back'])

# --- PAGE: DESIGN VAULT ---
elif page == "🎨 Design Vault":
    st.header("Design Link Manager")
    target_id = st.selectbox("Select Order ID", ["Select..."] + list(df['Order_ID'].unique()))
    
    if target_id != "Select...":
        idx = df[df['Order_ID'] == target_id].index[0]
        
        st.warning(f"Naming Guide: Save files as **{target_id}-image-front** and **{target_id}-image-back**")
        
        f_link = st.text_input("Paste 'Anyone with link' Link (Front)", value=df.at[idx, 'Image_front'])
        b_link = st.text_input("Paste 'Anyone with link' Link (Back)", value=df.at[idx, 'Image_back'])

        if st.button("💾 Save to Spreadsheet"):
            # Update local dataframe
            df.at[idx, 'Image_front'] = f_link if f_link else "None"
            df.at[idx, 'Image_back'] = b_link if b_link else "None"
            
            # Clean dataframe for update (removing helper columns if they exist)
            save_df = df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore')
            
            conn.update(data=save_df)
            st.success(f"Links for {target_id} updated!")
            st.rerun()
