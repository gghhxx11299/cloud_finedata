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
    
    # --- 2. DATA LOADING & MAPPING ---
    df = conn.read(ttl=0)
    
    # Ensure Date math works on your "Order Time" column
    df['Order Time'] = pd.to_datetime(df['Order Time'], errors='coerce').fillna(datetime.now())
    # Ensure Qty is a number for profit math
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(1)

    # --- 3. THE "LIFE EASIER" DASHBOARD ---
    st.title("🦅 Finedata Command Center")
    
    # Logic using your specific column names
    now = datetime.now()
    # 1-Hour Contact Warning
    late_contact = df[(df['Stage'] == 'Pending') & (df['Order Time'] < (now - timedelta(hours=1)))]
    # Payment Warning
    payment_hold = df[(df['Stage'] == 'Ready') & (df['Paid'] != 'Yes')]

    col1, col2, col3 = st.columns(3)
    with col1:
        if not late_contact.empty:
            st.error(f"🚨 {len(late_contact)} DELAYED CONTACTS (>1HR)")
        else: st.success("✅ Response Time: Excellent")
    with col2:
        if not payment_hold.empty:
            st.warning(f"💳 {len(payment_hold)} READY BUT UNPAID")
    with col3:
        # Business Data: 800 ETB profit per card
        total_profit = (df['Qty'].sum() * 800)
        st.metric("Total Net Profit", f"{total_profit:,} ETB")

    st.divider()

    # --- 4. OPERATIONS HUB ---
    tab1, tab2 = st.tabs(["🏗️ Production & Workflow", "📝 Manual Order Entry"])

    with tab1:
        st.subheader("Live Pipeline")
        # Search by your Order_ID or Contact
        search = st.text_input("🔍 Search Order_ID or Phone")
        display_df = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
        
        # Interactive Editor mapped to your columns
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Stage": st.column_config.SelectboxColumn(
                    "Production Stage", 
                    options=["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"]
                ),
                "Paid": st.column_config.SelectboxColumn(
                    "Payment Confirmed", options=["Yes", "No", "Partial"]
                ),
                "Order Time": st.column_config.DatetimeColumn("Order Time", format="D MMM, h:mm a"),
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("🚀 Push Changes to Cloud"):
            conn.update(data=edited_df)
            st.success("Cloud Synchronized!")
            st.rerun()

    with tab2:
        with st.form("manual_order"):
            st.subheader("New Customer Registration")
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            phone = c2.text_input("Contact")
            qty = st.number_input("Qty", min_value=1)
            # Match your money column (Price calculation)
            price = qty * 1200
            
            if st.form_submit_button("Register Order"):
                new_row = pd.DataFrame([{
                    "Order Time": datetime.now(), 
                    "Order_ID": f"MAN-{datetime.now().strftime('%m%d%H%M')}", 
                    "Name": name,
                    "Contact": phone, 
                    "Qty": qty, 
                    "money": price,
                    "Paid": "No", 
                    "Stage": "Pending",
                    "Total": price,
                    "Biker": "Unassigned"
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success("New order added to Excel!")
                st.rerun()
