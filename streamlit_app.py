import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CORE SETTINGS ---
st.set_page_config(page_title="FINEDA TREASURY", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData HQ Login")
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Access"):
            if pwd == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Denied")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0).astype(str)

    # Clean Data
    df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
    df['Order Time'] = pd.to_datetime(df['Order Time'], errors='coerce')
    now = datetime.now()

    # --- 2. SIDEBAR ---
    page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs", "📝 New Entry"])

    # --- 3. PAGE: DASHBOARD (FINANCIALS) ---
    if page == "📊 Dashboard":
        st.header("Financial & Operational Intelligence")
        
        # --- 🏦 TREASURY SECTION ---
        st.subheader("💰 Treasury & Cash Flow")
        
        # 1. Money on hand (Paid total)
        cash_on_hand = df[df['Paid'] == 'Yes']['Total_num'].sum()
        
        # 2. Money left to collect (Unpaid/Partial)
        receivables = df[df['Paid'] != 'Yes']['Total_num'].sum()
        
        # 3. Money owed to suppliers (400 ETB per card produced)
        # Assuming production starts when stage is 'Printing' or further
        produced_qty = df[df['Stage'].isin(['Printing', 'Ready', 'Delivered'])]['Qty_num'].sum()
        supplier_debt = produced_qty * 400
        
        # 4. Net Liquid Cash (Cash on hand minus what you owe suppliers)
        net_liquid = cash_on_hand - supplier_debt

        f1, f2, f3 = st.columns(3)
        f1.metric("💵 Cash on Hand", f"{cash_on_hand:,} ETB", help="Total collected from 'Paid' orders")
        f2.metric("⏳ To be Collected", f"{receivables:,} ETB", help="Money still sitting with customers")
        f3.metric("🏭 Supplier Debt", f"{supplier_debt:,} ETB", help="400 ETB x Total cards produced", delta_color="inverse", delta=f"-{supplier_debt}")

        st.info(f"💡 **Net Profit after Supplier Pay:** {net_liquid:,} ETB")
        
        st.divider()

        # --- OPERATIONAL METRICS ---
        st.subheader("🏗️ Workflow Metrics")
        m1, m2, m3 = st.columns(3)
        m1.metric("Ready/Unsent", len(df[(df['Stage'] == 'Ready') & (df['Paid'] == 'Yes')]))
        m2.metric("Delivered", len(df[df['Stage'] == 'Delivered']))
        m3.metric("Prod/Design Done", len(df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'Yes')]))
        
        m4, m5 = st.columns(2)
        m4.metric("Design Pending", len(df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'No')]))
        m5.metric("Total Order Queue", len(df))

        st.divider()

        # --- DEADLINE TABLE ---
        st.subheader("⏳ Deadline Tracking")
        def get_status(row):
            if pd.isna(row['Order Time']): return "⚪ No Date", "⚪ No Date"
            p_rem = ((row['Order Time'] + timedelta(days=4)) - now).days
            d_rem = ((row['Order Time'] + timedelta(days=7)) - now).days
            p_f = f"🔴 LATE" if p_rem < 0 else (f"🟡 URGENT" if p_rem <= 1 else f"🟢 {p_rem}d")
            d_f = f"🔴 LATE" if d_rem < 0 else (f"🟡 URGENT" if d_rem <= 1 else f"🟢 {d_rem}d")
            return p_f, d_f

        df['Production'], df['Delivery'] = zip(*df.apply(get_status, axis=1))
        st.table(df[['Order_ID', 'Name', 'Stage', 'Production', 'Delivery']])

    # --- 4. LOGS & EDIT --- (Including Delete & Status Edits)
    elif page == "📜 Order Logs":
        st.subheader("Manage Database")
        order_id = st.selectbox("Edit Order ID", ["Select..."] + list(df['Order_ID'].unique()))
        
        if order_id != "Select...":
            idx = df[df['Order_ID'] == order_id].index[0]
            with st.form("edit"):
                c1, c2 = st.columns(2)
                u_stage = c1.selectbox("Stage", ["Pending", "Printing", "Ready", "Delivered"], index=0)
                u_paid = c2.selectbox("Paid", ["No", "Yes", "Partial"], index=0)
                u_biker = c1.text_input("Biker", value=df.at[idx, 'Biker'])
                
                if st.form_submit_button("Save"):
                    df.at[idx, 'Stage'] = u_stage
                    df.at[idx, 'Paid'] = u_paid
                    df.at[idx, 'Biker'] = u_biker
                    conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Production', 'Delivery'], errors='ignore'))
                    st.success("Updated")
                    st.rerun()

    # --- 5. NEW ENTRY ---
    elif page == "📝 New Entry":
        with st.form("new"):
            st.subheader("Add Order")
            n_id = st.text_input("Order ID")
            n_name = st.text_input("Name")
            n_qty = st.number_input("Qty", min_value=1)
            if st.form_submit_button("Submit"):
                new_row = pd.DataFrame([{
                    "Order Time": now.strftime("%Y-%m-%d %H:%M"),
                    "Order_ID": n_id, "Name": n_name, "Qty": str(n_qty),
                    "money": str(n_qty*1200), "Paid": "No", "Stage": "Pending",
                    "Total": str(n_qty*1200), "Biker": "Unassigned",
                    "Design_confirmed": "No", "Is_connected_designer": "No", "Designer_finished": "No"
                }])
                conn.update(data=pd.concat([df.drop(columns=['Qty_num','Total_num','Production','Delivery'], errors='ignore'), new_row]))
                st.rerun()
