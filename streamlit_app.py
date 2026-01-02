import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. CORE SETTINGS ---
st.set_page_config(page_title="FINEDA HQ v3.0", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData HQ Login")
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Access System"):
            if pwd == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Access Denied")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0).astype(str)

    # --- 2. SIDEBAR NAVIGATION ---
    st.sidebar.title("🎮 Command Center")
    page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs & Edit", "📝 New Entry"])
    
    if st.sidebar.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    # --- 3. PAGE: DASHBOARD (METRICS) ---
    if page == "📊 Dashboard":
        st.header("Business Intelligence")
        
        # Calculations
        total_orders = len(df)
        pending = len(df[df['Stage'] == 'Pending'])
        ready = len(df[df['Stage'] == 'Ready'])
        design_queue = len(df[df['Is_connected_designer'] == 'Yes'])
        revenue = pd.to_numeric(df['Total'], errors='coerce').sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders", total_orders)
        m2.metric("Pending Queue", pending, delta=f"{pending} active", delta_color="inverse")
        m3.metric("Ready to Ship", ready)
        m4.metric("Gross Revenue", f"{revenue:,} ETB")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Stage Breakdown")
            st.bar_chart(df['Stage'].value_counts())
        with col_b:
            st.subheader("Design Status")
            st.write(f"🎨 **Need Designer:** {len(df[df['Is_connected_designer'] == 'Yes'])}")
            st.write(f"✅ **Designs Finished:** {len(df[df['Designer_finished'] == 'Yes'])}")

    # --- 4. PAGE: ORDER LOGS & EDIT ---
    elif page == "📜 Order Logs & Edit":
        st.header("Order Management & Forensics")
        
        search = st.text_input("🔍 Search any ID, Name, or Phone")
        display_df = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🛠️ Edit or Delete Order")
        order_id = st.selectbox("Select Order ID", options=["Select..."] + list(df['Order_ID'].unique()))
        
        if order_id != "Select...":
            row_idx = df[df['Order_ID'] == order_id].index[0]
            curr = df.loc[row_idx]
            
            with st.form("edit_form"):
                c1, c2, c3 = st.columns(3)
                # Design Workflow Columns
                d_conf = c1.selectbox("Design Confirmed?", ["No", "Yes"], index=0 if curr.get('Design_confirmed') != 'Yes' else 1)
                d_conn = c2.selectbox("Needs Designer?", ["No", "Yes"], index=0 if curr.get('Is_connected_designer') != 'Yes' else 1)
                d_fin = c3.selectbox("Design Finished?", ["No", "Yes"], index=0 if curr.get('Designer_finished') != 'Yes' else 1)
                
                # Logistics
                u_stage = c1.selectbox("Stage", ["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"], index=0)
                u_paid = c2.selectbox("Paid", ["No", "Yes", "Partial"], index=0)
                u_biker = c3.text_input("Biker", value=curr['Biker'])
                
                col_save, col_del = st.columns([5, 1])
                if col_save.form_submit_button("💾 Save Changes"):
                    df.at[row_idx, 'Design_confirmed'] = d_conf
                    df.at[row_idx, 'Is_connected_designer'] = d_conn
                    df.at[row_idx, 'Designer_finished'] = d_fin
                    df.at[row_idx, 'Stage'] = u_stage
                    df.at[row_idx, 'Paid'] = u_paid
                    df.at[row_idx, 'Biker'] = u_biker
                    conn.update(data=df)
                    st.success("Updated!")
                    st.rerun()
                
                if col_del.form_submit_button("🗑️ DELETE"):
                    df = df.drop(row_idx)
                    conn.update(data=df)
                    st.warning("Order Deleted.")
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
            
            # New Designer Checkboxes
            n_conn = st.checkbox("Customer needs a Designer")
            
            if st.form_submit_button("🚀 Add to Cloud"):
                price = n_qty * 1200
                new_row = pd.DataFrame([{
                    "Order Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Order_ID": n_id if n_id else f"MAN-{datetime.now().strftime('%M%S')}",
                    "Name": n_name, "Contact": n_phone, "Qty": str(n_qty),
                    "money": str(price), "Paid": "No", "Stage": "Pending", "Total": str(price), 
                    "Biker": "Unassigned", "Design_confirmed": "No", 
                    "Is_connected_designer": "Yes" if n_conn else "No", 
                    "Designer_finished": "No"
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=df)
                st.success("Order Logged!")
