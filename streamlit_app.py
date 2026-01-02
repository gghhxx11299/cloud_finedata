import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- AUTHENTICATION LOGIC ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show login
        st.title("🛡️ Finedata Cloud Login")
        st.text_input("Admin Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.title("🛡️ Finedata Cloud Login")
        st.text_input("Admin Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

if check_password():
    # --- APP STARTS HERE ---
    st.set_page_config(page_title="FINEDA HQ", layout="wide")
    
    # 1. Connect & Load Data
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)

    # 2. Advanced Sidebar
    st.sidebar.title("⚓ Command Center")
    st.sidebar.info(f"Logged in as: **Admin**")
    
    app_mode = st.sidebar.radio("Navigate", ["📈 Executive Suite", "🛠️ Production Floor", "🚚 Logistics Hub"])
    
    if st.sidebar.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    # --- MODE 1: EXECUTIVE SUITE ---
    if app_mode == "📈 Executive Suite":
        st.header("Financial Intelligence")
        
        # Complex Metrics
        m1, m2, m3 = st.columns(3)
        total_rev = (df['Qty'].astype(int) * 1200).sum()
        total_profit = len(df) * 800
        
        m1.metric("Gross Revenue", f"{total_rev:,} ETB")
        m2.metric("Net Profit (800/unit)", f"{total_profit:,} ETB", delta="Live")
        m3.metric("Efficiency", "94%", delta="Target 98%")
        
        st.subheader("Master Data Ledger")
        st.dataframe(df, use_container_width=True)

    # --- MODE 2: PRODUCTION FLOOR ---
    elif app_mode == "🛠️ Production Floor":
        st.header("Manufacturing Queue")
        
        # Filter only what needs work
        work_df = df[df['Status'].isin(["Pending", "Printing"])]
        
        edited_df = st.data_editor(
            work_df,
            use_container_width=True,
            column_config={
                "Status": st.column_config.SelectboxColumn("Stage", options=["Pending", "Printing", "Ready"]),
                "Payment": st.column_config.CheckboxColumn("Verified?")
            }
        )
        
        if st.button("Update Cloud"):
            df.update(edited_df)
            conn.update(data=df)
            st.success("Production status synced.")

    # --- MODE 3: LOGISTICS HUB ---
    elif app_mode == "🚚 Logistics Hub":
        st.header("Delivery Management")
        ready_df = df[df['Status'] == "Ready"]
        
        if ready_df.empty:
            st.info("No orders ready for delivery yet.")
        else:
            st.data_editor(ready_df[["Name", "Contact", "Qty", "Status"]])
