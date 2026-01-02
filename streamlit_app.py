import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SETTINGS & AUTH ---
st.set_page_config(page_title="FINEDA HQ", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData Secure Gate")
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Unlock"):
            if pwd == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Wrong Password")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # --- 2. DATA SANITIZER (Prevents KeyErrors) ---
    raw_df = conn.read(ttl=0)
    
    # Define exactly what your business needs
    required_columns = ["Date", "Order_ID", "Name", "Contact", "Qty", "Payment", "Status", "Biker"]
    
    if raw_df is None or raw_df.empty:
        df = pd.DataFrame(columns=required_columns)
    else:
        df = raw_df.copy()
        for col in required_columns:
            if col not in df.columns:
                df[col] = "Missing" # Auto-fill missing columns so code doesn't crash

    # Force Date conversion safely
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').fillna(datetime.now())
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(1)

    # --- 3. THE "LIFE EASIER" DASHBOARD ---
    st.title("🦅 Finedata Command Center")
    
    # Smart Alerts: Contact within 1hr & Unpaid Ready orders
    now = datetime.now()
    late_contact = df[(df['Status'] == 'Pending') & (df['Date'] < (now - timedelta(hours=1)))]
    payment_hold = df[(df['Status'] == 'Ready') & (df['Payment'] != 'Paid')]

    col1, col2, col3 = st.columns(3)
    with col1:
        if not late_contact.empty:
            st.error(f"🚨 {len(late_contact)} CUSTOMERS WAITING >1HR")
        else: st.success("✅ Contact Response Time: Good")
    with col2:
        if not payment_hold.empty:
            st.warning(f"💳 {len(payment_hold)} READY BUT UNPAID")
    with col3:
        profit = (df['Qty'].sum() * 800)
        st.metric("Total Net Profit", f"{profit:,} ETB")

    st.divider()

    # --- 4. OPERATIONS & BOT SYNC ---
    tab1, tab2 = st.tabs(["🏗️ Production & Workflow", "📝 Manual Order Entry"])

    with tab1:
        st.subheader("Live Pipeline")
        # Search by Bot Order ID
        search = st.text_input("🔍 Search Order ID or Phone")
        display_df = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Stage", options=["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"]
                ),
                "Payment": st.column_config.SelectboxColumn(
                    "Money", options=["Paid", "Unpaid", "Telebirr Pending"]
                ),
                "Date": st.column_config.DatetimeColumn("Order Time", format="D MMM, h:mm a"),
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("🚀 Sync Changes to Cloud"):
            conn.update(data=edited_df)
            st.success("Cloud Updated!")
            st.rerun()

    with tab2:
        with st.form("manual_order"):
            st.subheader("New Customer Registration")
            c1, c2 = st.columns(2)
            new_name = c1.text_input("Name")
            new_phone = c2.text_input("Phone")
            new_qty = st.number_input("Quantity", min_value=1)
            new_id = f"MAN-{datetime.now().strftime('%m%d%H%M')}"
            
            if st.form_submit_button("Register Order"):
                new_row = pd.DataFrame([{
                    "Date": datetime.now(), "Order_ID": new_id, "Name": new_name,
                    "Contact": new_phone, "Qty": new_qty, "Payment": "Unpaid", "Status": "Pending"
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=df)
                st.rerun()
