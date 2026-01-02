import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CORE SETTINGS ---
st.set_page_config(page_title="FINEDA OPERATIONS", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData HQ Login")
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Access System"):
            if pwd == st.secrets.auth.password:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Access Denied")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0).astype(str)

    # --- DATA PREP ---
    df['Order Time'] = pd.to_datetime(df['Order Time'], errors='coerce')
    df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    now = datetime.now()

    # --- 2. SIDEBAR NAVIGATION ---
    st.sidebar.title("🎮 Command Center")
    page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs & Edit", "📝 New Entry"])
    
    # --- 3. PAGE: DASHBOARD (ADVANCED METRICS) ---
    if page == "📊 Dashboard":
        st.header("Business Operations & Logic")
        
        # Specific Metric Calculations
        finished_not_delivered = df[(df['Stage'] == 'Ready') & (df['Paid'] == 'Yes')]
        finished_delivered = df[df['Stage'] == 'Delivered']
        not_fin_design_done = df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'Yes')]
        not_fin_design_not_done = df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'No')]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("📦 Ready (Not Delivered)", len(finished_not_delivered))
        m2.metric("✅ Delivery Completed", len(finished_delivered))
        m3.metric("🏗️ Design Done (In Production)", len(not_fin_design_done))
        
        m4, m5, m6 = st.columns(3)
        m4.metric("🎨 Design Pending", len(not_fin_design_not_done))
        m5.metric("📈 Total Order Queue", len(df))
        m6.metric("💎 VIP Orders (>3)", len(df[df['Qty_num'] > 3]))

        st.divider()
        
        # --- TIME TRACKING LOGIC ---
        st.subheader("⏳ Production & Delivery Deadlines")
        
        def calculate_status(row):
            order_date = row['Order Time']
            # Deadlines
            prod_deadline = order_date + timedelta(days=4)
            deliv_deadline = order_date + timedelta(days=7) # 4 days prod + 3 days delivery
            
            # Time Remaining
            time_to_prod = (prod_deadline - now).days
            time_to_deliv = (deliv_deadline - now).days
            
            # Color Logic
            if row['Stage'] == 'Delivered':
                return "🟢 Complete", "🟢 Complete"
            
            # Production Flag
            if time_to_prod < 0: p_flag = f"🔴 LATE ({abs(time_to_prod)} days)"
            elif time_to_prod <= 1: p_flag = f"🟡 URGENT ({time_to_prod} days)"
            else: p_flag = f"🟢 {time_to_prod} days left"
            
            # Delivery Flag
            if time_to_deliv < 0: d_flag = f"🔴 LATE ({abs(time_to_deliv)} days)"
            elif time_to_deliv <= 1: d_flag = f"🟡 URGENT ({time_to_deliv} days)"
            else: d_flag = f"🟢 {time_to_deliv} days left"
            
            return p_flag, d_flag

        # Apply flags to a summary view
        df['Production_Status'], df['Delivery_Status'] = zip(*df.apply(calculate_status, axis=1))
        
        st.table(df[['Order_ID', 'Name', 'Stage', 'Production_Status', 'Delivery_Status']].sort_values('Order Time'))

    # --- 4. PAGE: ORDER LOGS & EDIT ---
    elif page == "📜 Order Logs & Edit":
        st.header("Order Management")
        search = st.text_input("🔍 Search Name/ID/Phone")
        display_df = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
        st.dataframe(display_df.drop(columns=['Qty_num']), use_container_width=True, hide_index=True)
        
        st.divider()
        order_id = st.selectbox("Edit Order ID", options=["Select..."] + list(df['Order_ID'].unique()))
        
        if order_id != "Select...":
            row_idx = df[df['Order_ID'] == order_id].index[0]
            curr = df.loc[row_idx]
            
            with st.form("edit_form"):
                c1, c2, c3 = st.columns(3)
                d_conf = c1.selectbox("Design Confirmed?", ["No", "Yes"], index=1 if curr.get('Design_confirmed') == 'Yes' else 0)
                d_conn = c2.selectbox("Needs Designer?", ["No", "Yes"], index=1 if curr.get('Is_connected_designer') == 'Yes' else 0)
                d_fin = c3.selectbox("Design Finished?", ["No", "Yes"], index=1 if curr.get('Designer_finished') == 'Yes' else 0)
                
                u_stage = c1.selectbox("Stage", ["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"])
                u_paid = c2.selectbox("Paid", ["No", "Yes", "Partial"])
                u_biker = c3.text_input("Biker", value=curr['Biker'])
                
                col_save, col_del = st.columns([5, 1])
                if col_save.form_submit_button("💾 Save Changes"):
                    df.at[row_idx, 'Design_confirmed'] = d_conf
                    df.at[row_idx, 'Is_connected_designer'] = d_conn
                    df.at[row_idx, 'Designer_finished'] = d_fin
                    df.at[row_idx, 'Stage'] = u_stage
                    df.at[row_idx, 'Paid'] = u_paid
                    df.at[row_idx, 'Biker'] = u_biker
                    conn.update(data=df.drop(columns=['Qty_num', 'Production_Status', 'Delivery_Status'], errors='ignore'))
                    st.success("Updated!")
                    st.rerun()
                
                if col_del.form_submit_button("🗑️ DELETE"):
                    df = df.drop(row_idx)
                    conn.update(data=df.drop(columns=['Qty_num', 'Production_Status', 'Delivery_Status'], errors='ignore'))
                    st.warning("Deleted.")
                    st.rerun()

    # --- 5. PAGE: NEW ENTRY ---
    elif page == "📝 New Entry":
        st.header("Register New Order")
        with st.form("new_entry_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n_id = c1.text_input("Order_ID")
            n_name = c2.text_input("Customer Name")
            n_phone = c1.text_input("Contact")
            n_qty = c2.number_input("Quantity", min_value=1, value=1)
            n_conn = st.checkbox("Needs Designer")
            
            if st.form_submit_button("🚀 Add to Cloud"):
                price = n_qty * 1200
                new_row = pd.DataFrame([{
                    "Order Time": now.strftime("%Y-%m-%d %H:%M"),
                    "Order_ID": n_id if n_id else f"MAN-{now.strftime('%M%S')}",
                    "Name": n_name, "Contact": n_phone, "Qty": str(n_qty),
                    "money": str(price), "Paid": "No", "Stage": "Pending", "Total": str(price), 
                    "Biker": "Unassigned", "Design_confirmed": "No", 
                    "Is_connected_designer": "Yes" if n_conn else "No", 
                    "Designer_finished": "No"
                }])
                final_df = pd.concat([df.drop(columns=['Qty_num', 'Production_Status', 'Delivery_Status'], errors='ignore'), new_row], ignore_index=True)
                conn.update(data=final_df)
                st.success("Logged!")
