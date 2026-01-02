import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SETTINGS ---
st.set_page_config(page_title="FINEDA HQ", layout="wide")

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

    # Clean Data for Logic
    df['Order Time'] = pd.to_datetime(df['Order Time'], errors='coerce')
    df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    now = datetime.now()

    # --- 2. SIDEBAR ---
    page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs", "📝 New Entry"])

    # --- 3. DASHBOARD ---
    if page == "📊 Dashboard":
        st.header("Business Operations")
        
        # Metrics Logic
        f_not_d = df[(df['Stage'] == 'Ready') & (df['Paid'] == 'Yes')]
        f_d = df[df['Stage'] == 'Delivered']
        nf_ds_y = df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'Yes')]
        nf_ds_n = df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'No')]

        c1, c2, c3 = st.columns(3)
        c1.metric("Ready/Unsent", len(f_not_d))
        c2.metric("Delivered", len(f_d))
        c3.metric("Prod/Design Done", len(nf_ds_y))
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Design Pending", len(nf_ds_n))
        c5.metric("Total Queue", len(df))
        c6.metric("VIP (>3)", len(df[df['Qty_num'] > 3]))

        st.divider()
        st.subheader("⏳ Deadlines")

        def get_status(row):
            if pd.isna(row['Order Time']): return "⚪ No Date", "⚪ No Date"
            p_due = row['Order Time'] + timedelta(days=4)
            d_due = row['Order Time'] + timedelta(days=7)
            
            p_rem = (p_due - now).days
            d_rem = (d_due - now).days
            
            p_flag = f"🔴 LATE" if p_rem < 0 else (f"🟡 URGENT" if p_rem <= 1 else f"🟢 {p_rem}d")
            d_flag = f"🔴 LATE" if d_rem < 0 else (f"🟡 URGENT" if d_rem <= 1 else f"🟢 {d_rem}d")
            return p_flag, d_flag

        df['Production'], df['Delivery'] = zip(*df.apply(get_status, axis=1))
        
        # FIXED: Ensure column exists before display
        view_cols = ['Order_ID', 'Name', 'Stage', 'Production', 'Delivery']
        st.table(df[view_cols])

    # --- 4. LOGS & EDIT ---
    elif page == "📜 Order Logs":
        search = st.text_input("🔍 Search")
        filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
        st.dataframe(filtered.drop(columns=['Qty_num', 'Production', 'Delivery'], errors='ignore'))
        
        order_id = st.selectbox("Edit Order ID", ["Select..."] + list(df['Order_ID'].unique()))
        if order_id != "Select...":
            idx = df[df['Order_ID'] == order_id].index[0]
            with st.form("edit"):
                col1, col2 = st.columns(2)
                u_stage = col1.selectbox("Stage", ["Pending", "Printing", "Ready", "Delivered"])
                u_paid = col2.selectbox("Paid", ["No", "Yes", "Partial"])
                u_biker = col1.text_input("Biker", value=df.at[idx, 'Biker'])
                
                # Design status
                d_conf = col1.checkbox("Design Confirmed", value=(df.at[idx, 'Design_confirmed'] == 'Yes'))
                d_conn = col2.checkbox("Needs Designer", value=(df.at[idx, 'Is_connected_designer'] == 'Yes'))
                d_fin = col2.checkbox("Design Finished", value=(df.at[idx, 'Designer_finished'] == 'Yes'))

                if st.form_submit_button("Save"):
                    df.at[idx, 'Stage'] = u_stage
                    df.at[idx, 'Paid'] = u_paid
                    df.at[idx, 'Biker'] = u_biker
                    df.at[idx, 'Design_confirmed'] = "Yes" if d_conf else "No"
                    df.at[idx, 'Is_connected_designer'] = "Yes" if d_conn else "No"
                    df.at[idx, 'Designer_finished'] = "Yes" if d_fin else "No"
                    
                    # Drop temporary columns before saving
                    save_df = df.drop(columns=['Qty_num', 'Production', 'Delivery', 'Order Time'], errors='ignore')
                    # Keep original Order Time strings
                    conn.update(data=save_df)
                    st.success("Saved")
                    st.rerun()

                if st.form_submit_button("🗑️ DELETE"):
                    df = df.drop(idx)
                    conn.update(data=df.drop(columns=['Qty_num', 'Production', 'Delivery'], errors='ignore'))
                    st.rerun()

    # --- 5. NEW ENTRY ---
    elif page == "📝 New Entry":
        with st.form("new"):
            n_id = st.text_input("Order ID")
            n_name = st.text_input("Name")
            n_qty = st.number_input("Qty", min_value=1)
            if st.form_submit_button("Add"):
                new_row = pd.DataFrame([{
                    "Order Time": now.strftime("%Y-%m-%d %H:%M"),
                    "Order_ID": n_id, "Name": n_name, "Qty": str(n_qty),
                    "money": str(n_qty*1200), "Paid": "No", "Stage": "Pending",
                    "Total": str(n_qty*1200), "Biker": "Unassigned",
                    "Design_confirmed": "No", "Is_connected_designer": "No", "Designer_finished": "No"
                }])
                conn.update(data=pd.concat([df.drop(columns=['Qty_num','Production','Delivery'], errors='ignore'), new_row]))
                st.rerun()
